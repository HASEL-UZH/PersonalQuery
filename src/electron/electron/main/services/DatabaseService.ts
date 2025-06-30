import { DataSource, DataSourceOptions } from 'typeorm';
import { app, dialog } from 'electron';
import path from 'path';
import { is } from './utils/helpers';
import getMainLogger from '../../config/Logger';
import { WindowActivityEntity } from '../entities/WindowActivityEntity';
import { ExperienceSamplingResponseEntity } from '../entities/ExperienceSamplingResponseEntity';
import { UserInputEntity } from '../entities/UserInputEntity';
import { Settings } from '../entities/Settings';
import { UsageDataEntity } from '../entities/UsageDataEntity';
import { WorkDayEntity } from '../entities/WorkDayEntity';
import { SessionEntity } from '../entities/SessionEntity';
import fs from 'node:fs';
import CoverageScore from '../../../shared/CoverageScore';
import {
  addWindowActivityDurations,
  performDatabaseMigration,
  updateSessionsFromUsageData
} from './dbMigration';
import Database from 'better-sqlite3';

const LOG = getMainLogger('DatabaseService');

export class DatabaseService {
  public dataSource: DataSource;
  private readonly dbPath: string;

  constructor() {
    const dbName = 'database.sqlite';
    this.dbPath = dbName;
    if (!(is.dev && process.env['VITE_DEV_SERVER_URL'])) {
      const userDataPath = app.getPath('userData');
      this.dbPath = path.join(userDataPath, dbName);
    }
    LOG.info('Using database path:', this.dbPath);
  }

  public async init(): Promise<void> {
    let entities: any = [
      ExperienceSamplingResponseEntity,
      SessionEntity,
      Settings,
      UsageDataEntity,
      UserInputEntity,
      WindowActivityEntity,
      WorkDayEntity
    ];

    let options: DataSourceOptions = {
      type: 'better-sqlite3',
      database: this.dbPath,
      synchronize: false,
      logging: false,
      entities: entities
    };

    this.dataSource = new DataSource(options);

    try {
      await this.dataSource.initialize();
      LOG.info('Database connection established');
    } catch (error) {
      LOG.error('Database connection failed', error);
    }
  }

  public async clearDatabase(): Promise<void> {
    try {
      LOG.info('Dropping database');
      await this.dataSource.dropDatabase();
      LOG.info('Database dropped');
      LOG.info('Synchronizing database');
      await this.dataSource.synchronize();
      LOG.info('Database synchronized');
      LOG.info('Database successfully cleared');
    } catch (error) {
      LOG.error('Database clearing failed', error);
    }
  }

  public async checkAndImportOldDataBase(): Promise<void> {
    const userDathaPath = app.getPath('userData');
    const targetPath = path.join(userDathaPath, 'database.sqlite');
    const sourcePath = path.join(app.getPath('appData'), 'personal-analytics', 'database.sqlite');

    const targetExists = fs.existsSync(targetPath);
    if (targetExists) {
      return;
    }

    const sourceExists = fs.existsSync(sourcePath);
    if (!sourceExists) {
      return;
    }

    const response = await dialog.showMessageBox({
      type: 'question',
      buttons: ['Yes', 'No'],
      defaultId: 0,
      cancelId: 1,
      title: 'Import Existing Data',
      message:
        'An existing PersonalAnalytics database was found. Do you want to import your old data?'
    });

    if (response.response === 0) {
      fs.copyFileSync(sourcePath, targetPath);
      LOG.info('Old PersonalAnalytics database copied into PersonalQuery');
      const db = new Database(targetPath);
      updateSessionsFromUsageData(db);
      addWindowActivityDurations(db);
    } else {
      LOG.info('User declined database import');
    }
  }

  private async runDataInit() {
    try {
      const res = await fetch('http://127.0.0.1:8000/initialize-data', {
        method: 'POST'
      });

      if (!res.ok) {
        const errorText = await res.text();
        LOG.error('Backend returned error during cleanup:', errorText);
      } else {
        LOG.info('Database modification via Python backend completed.');
      }
    } catch (e) {
      LOG.error('Failed to reach Python backend for cleanup:', e);
    }
  }

  public async getDataCoverageScore(): Promise<CoverageScore[]> {
    const windowActivity = await this.dataSource.query(`
    SELECT date(tsStart) AS day, COUNT(*) AS count
    FROM window_activity
    GROUP BY day
  `);

    const userInput = await this.dataSource.query(`
    SELECT date(tsStart) AS day, COUNT(*) AS count
    FROM user_input
    GROUP BY day
  `);

    const sessions = await this.dataSource.query(`
    SELECT date(tsStart) AS day, COUNT(*) AS count
    FROM session
    GROUP BY day
  `);

    const allDays = new Map<string, { wa: number; ui: number; s: number }>();

    for (const row of windowActivity) {
      allDays.set(row.day, { wa: row.count, ui: 0, s: 0 });
    }
    for (const row of userInput) {
      const entry = allDays.get(row.day) ?? { wa: 0, ui: 0, s: 0 };
      entry.ui = row.count;
      allDays.set(row.day, entry);
    }
    for (const row of sessions) {
      const entry = allDays.get(row.day) ?? { wa: 0, ui: 0, s: 0 };
      entry.s = row.count;
      allDays.set(row.day, entry);
    }

    // Convert to array with computed score
    const result: CoverageScore[] = Array.from(allDays.entries()).map(([day, counts]) => ({
      day,
      score: Math.round((counts.wa + counts.ui + counts.s * 10) / 100)
    }));

    // Sort descending by score
    result.sort((a, b) => b.score - a.score);

    return result;
  }
}
