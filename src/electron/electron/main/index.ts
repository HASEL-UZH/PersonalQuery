import 'reflect-metadata';
import { app, dialog, powerMonitor, systemPreferences } from 'electron';
import { release } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import log from 'electron-log/main';
import { getMainLogger } from '../config/Logger';
import { DatabaseService } from './services/DatabaseService';
import { SettingsService } from './services/SettingsService';
import { TrackerType } from '../enums/TrackerType.enum';
import { WindowActivityTrackerService } from './services/trackers/WindowActivityTrackerService';
import { UserInputTrackerService } from './services/trackers/UserInputTrackerService';
import { TrackerService } from './services/trackers/TrackerService';
import AppUpdaterService from './services/AppUpdaterService';
import { WindowService } from './services/WindowService';
import { IpcHandler } from '../ipc/IpcHandler';
import { ipcMain } from 'electron';
import { ExperienceSamplingService } from './services/ExperienceSamplingService';
import studyConfig from '../../shared/study.config';
import { is } from './services/utils/helpers';
import { Settings } from './entities/Settings';
import { UsageDataService } from './services/UsageDataService';
import { UsageDataEventType } from '../enums/UsageDataEventType.enum';
import { WorkScheduleService } from './services/WorkScheduleService';
import { spawn, exec } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { SessionService } from './services/SessionService';
import treeKill from 'tree-kill';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

process.env.DIST_ELECTRON = join(__dirname, '..');
process.env.DIST = join(process.env.DIST_ELECTRON, '../dist');
process.env.VITE_PUBLIC = process.env.VITE_DEV_SERVER_URL
  ? join(process.env.DIST_ELECTRON, '../public')
  : process.env.DIST;

const backendBinary = process.platform === 'win32' ? 'pq-backend.exe' : 'pq-backend';

const databaseService: DatabaseService = new DatabaseService();
const settingsService: SettingsService = new SettingsService();
const workScheduleService: WorkScheduleService = new WorkScheduleService();
const appUpdaterService: AppUpdaterService = new AppUpdaterService();
const windowService: WindowService = new WindowService(appUpdaterService);
const experienceSamplingService: ExperienceSamplingService = new ExperienceSamplingService();
const sessionService: SessionService = new SessionService();
const trackers: TrackerService = new TrackerService(
  studyConfig.trackers,
  windowService,
  workScheduleService
);
const ipcHandler: IpcHandler = new IpcHandler(
  windowService,
  trackers,
  experienceSamplingService,
  sessionService,
  workScheduleService,
  databaseService
);
const isDev = process.env.NODE_ENV === 'development';
let backendProcess: ReturnType<typeof spawn> | null = null;

function startBackend() {
  const backendExePath = path.join(process.resourcesPath, backendBinary);
  LOG.info(`Launching backend at: ${backendExePath}`);
  const newBackend = spawn(backendExePath, {
    cwd: path.dirname(backendExePath)
  });
  newBackend.stdout.on('data', (data) => {
    LOG.info(`[Backend STDOUT] ${data.toString().trim()}`);
  });
  newBackend.stderr.on('data', (data) => {
    LOG.error(`[Backend STDERR] ${data.toString().trim()}`);
  });
  newBackend.on('error', (err) => {
    LOG.error(`[Backend ERROR] ${err}`);
  });
  return newBackend;
}

function stopBackend(): void {
  if (!backendProcess) {
    return;
  }
  const pid = backendProcess.pid;
  LOG.info(`Sending SIGINT to backend process with PID: ${pid}`);

  treeKill(pid, "SIGINT", (err) => {
    if (err) {
      LOG.error(`Error sending SIGINT: ${err}`);
      return;
    }

    setTimeout(() => {
      try {
        process.kill(pid, 0);
        LOG.warn(`Backend PID ${pid} still alive, sending SIGKILL`);
        treeKill(pid, "SIGKILL", (killErr) => {
          if (killErr) {
            LOG.error(`Error sending SIGKILL: ${killErr}`);
          } else {
            LOG.info(`SIGKILL successfully sent to PID ${pid}`);
          }
        });
      } catch (e) {
        LOG.info(`Backend PID ${pid} has already exited.`);
      }
    }, 2000);
  });

  backendProcess = null;
}

globalThis.backendProcess = backendProcess;

/* eslint-disable no-var */
declare global {
  var backendProcess: ReturnType<typeof spawn> | null;
}
/* eslint-enable no-var */

// Disable GPU Acceleration for Windows 7
if (release().startsWith('6.1')) {
  app.disableHardwareAcceleration();
}

// Set application name for Windows 10+ notifications
if (process.platform === 'win32') {
  app.setAppUserModelId(app.getName());
}

if (!isDev && !app.requestSingleInstanceLock()) {
  console.log('Another instance of the app is already running');
  app.quit();
  process.exit(0);
}

if (is.macOS) {
  app.dock.hide();
}

// Optional, initialize the logger for any renderer process
log.initialize();
const LOG = getMainLogger('Main');

app.whenReady().then(async () => {
  await ipcHandler.init();
  app.setAppUserModelId('ch.ifi.hasel.personalquery');
  if (!is.dev) {
    const envPath = path.join(process.resourcesPath, '.env');
    if (!fs.existsSync(envPath)) {
      LOG.info('.env file not found, prompting user to create one.');
      await windowService.createEnvSetupWindow();
      LOG.info('.env setup window completed.');
    }
    backendProcess = startBackend();

    app.setLoginItemSettings({
      openAtLogin: true,
      args: ['--hidden'] // Using this flag to detect auto-launch
    });
  } else {
    LOG.info('Skip setting openAtLogin because app is running in development mode');
  }

  try {
    await databaseService.checkAndImportOldDataBase();
    await databaseService.init();
    await workScheduleService.init();
    await settingsService.init();
    await windowService.init();

    const currentTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const currentLocale = app.getLocale();
    const currentDateUTC = new Date();
    const appVersion = app.getVersion();
    const startupData = {
      appVersion,
      currentTimeZone,
      currentLocale,
      currentDateUTC
    };
    LOG.info(
      `App started (Version: ${appVersion}). Timezone: ${currentTimeZone}, Locale: ${currentLocale}, UTC: ${currentDateUTC}`
    );
    UsageDataService.createNewUsageDataEvent(
      UsageDataEventType.AppStart,
      JSON.stringify(startupData)
    );

    await appUpdaterService.checkForUpdates({ silent: true });
    appUpdaterService.startCheckForUpdatesInterval();
    if (!isDev) {
      if (studyConfig.trackers.windowActivityTracker.enabled) {
        await trackers.registerTrackerCallback(
          TrackerType.WindowsActivityTracker,
          WindowActivityTrackerService.handleWindowChange
        );
      }
      if (studyConfig.trackers.userInputTracker.enabled) {
        await trackers.registerTrackerCallback(
          TrackerType.UserInputTracker,
          UserInputTrackerService.handleUserInputEvent
        );
      }
      if (studyConfig.trackers.experienceSamplingTracker.enabled) {
        await trackers.registerTrackerCallback(TrackerType.ExperienceSamplingTracker);
      }

      if (studyConfig.displayDaysParticipated) {
        await trackers.registerTrackerCallback(TrackerType.DaysParticipatedTracker);
      }
    }

    const settings: Settings = await Settings.findOneBy({ onlyOneEntityShouldExist: 1 });
    const isAutoLaunch =
      app.getLoginItemSettings().wasOpenedAtLogin || process.argv.includes('--hidden');

    // show onboarding window (if never shown or macOS permissions are missing)
    if (
      settings.onboardingShown === false ||
      !macOSHasAccessibilityAndScreenRecordingPermission()
    ) {
      LOG.debug(
        `Onboarding shown: ${settings.onboardingShown}, hasAccessibilityAndScreenRecordingPermission: ${macOSHasAccessibilityAndScreenRecordingPermission()}, creating onboarding window...`
      );
      //await windowService.createOnboardingWindow(); FIXME
      settings.onboardingShown = true;
      await settings.save();

      // show PA running page when it was not shown before (on macOS) OR if it was manually started
    } else if (
      (is.macOS &&
        settings.onboardingShown === true &&
        settings.studyAndTrackersStartedShown === false) ||
      !isAutoLaunch
    ) {
      //await windowService.createOnboardingWindow('study-trackers-started'); FIXME
      settings.studyAndTrackersStartedShown = true;
      await settings.save();
    }

    if (!is.macOS || macOSHasAccessibilityAndScreenRecordingPermission()) {
      LOG.debug(
        `Onboarding shown: ${settings.onboardingShown}, hasAccessibilityAndScreenRecordingPermission: ${macOSHasAccessibilityAndScreenRecordingPermission()}, starting all trackers...`
      );
      await trackers.startAllTrackers();
      LOG.info(`Trackers started: ${trackers.getRunningTrackerNames().join(', ')}`);

      powerMonitor.on('suspend', async (): Promise<void> => {
        LOG.debug('The system is going to sleep');
        await Promise.all([
          trackers.stopAllTrackers(),
          UsageDataService.createNewUsageDataEvent(UsageDataEventType.SystemSuspend)
        ]);
      });
      powerMonitor.on('resume', async (): Promise<void> => {
        LOG.debug('The system is resuming');
        await Promise.all([
          trackers.resumeAllTrackers(),
          UsageDataService.createNewUsageDataEvent(UsageDataEventType.SystemResume)
        ]);
      });
      powerMonitor.on('shutdown', async (): Promise<void> => {
        LOG.debug('The system is going to shutdown');
        await Promise.all([
          trackers.stopAllTrackers(),
          UsageDataService.createNewUsageDataEvent(UsageDataEventType.SystemShutdown)
        ]);
      });
      powerMonitor.on('lock-screen', async (): Promise<void> => {
        LOG.debug('The system is going to lock-screen');
        await Promise.all([
          trackers.stopAllTrackers(),
          UsageDataService.createNewUsageDataEvent(UsageDataEventType.SystemLockScreen)
        ]);
      });
      powerMonitor.on('unlock-screen', async (): Promise<void> => {
        LOG.debug('The system is going to unlock-screen');
        await Promise.all([
          trackers.resumeAllTrackers(),
          UsageDataService.createNewUsageDataEvent(UsageDataEventType.SystemUnlockScreen)
        ]);
      });
    }
  } catch (error) {
    LOG.error('Error during app initialization', error);
    dialog.showErrorBox(
      'Error during app initialization',
      `PersonalQuery couldn't be started. Please try again or contact us at ${studyConfig.contactEmail} for help. ${error}`
    );
    app.exit();
  }
});

let isAppQuitting = false;
app.on('before-quit', async (event): Promise<void> => {
  stopBackend();
  LOG.info('app.on(before-quit) called');
  if (!isAppQuitting) {
    event.preventDefault();
    LOG.info(`Stopping all (${trackers.getRunningTrackerNames().join(', ')}) trackers...`);
    await Promise.all([
      trackers.stopAllTrackers(),
      UsageDataService.createNewUsageDataEvent(UsageDataEventType.AppQuit),
      sessionService.createOrUpdateSessionFromEvent(UsageDataEventType.AppQuit, new Date()),
      WindowActivityTrackerService.finalizeCurrentWindow()
    ]);
    LOG.info(`All trackers stopped. Running: ${trackers.getRunningTrackerNames().length}`);
    isAppQuitting = true;
    app.exit();
  }
});

// Don't quit when all windows are closed
app.on('window-all-closed', () => {});

function macOSHasAccessibilityAndScreenRecordingPermission(): boolean {
  if (!is.macOS) {
    return true;
  }

  return (
    systemPreferences.isTrustedAccessibilityClient(false) &&
    systemPreferences.getMediaAccessStatus('screen') === 'granted'
  );
}
