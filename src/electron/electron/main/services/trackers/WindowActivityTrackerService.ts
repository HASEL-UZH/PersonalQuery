import ActiveWindow from 'windows-activity-tracker/dist/types/ActiveWindow';
import { WindowActivityEntity } from '../../entities/WindowActivityEntity';
import { DeepPartial, In } from 'typeorm';
import getMainLogger from '../../../config/Logger';
import WindowActivityDto from '../../../../shared/dto/WindowActivityDto';

const LOG = getMainLogger('WindowActivityTrackerService');
const MAX_DURATION = 3600;

export class WindowActivityTrackerService {
  private randomStringMap: Map<string, string> = new Map<string, string>();
  private static prevWindowTsStart: Date;
  private static prevWindowId: string;

  public static async handleWindowChange(window: ActiveWindow): Promise<void> {
    if (!window.windowTitle && !window.url) {
      return;
    }
    if (this.prevWindowId && this.prevWindowTsStart) {
      const duration = Math.floor((window.ts.getTime() - this.prevWindowTsStart.getTime()) / 1000);

      const finalDuration = Math.min(duration, MAX_DURATION);

      await WindowActivityEntity.update(this.prevWindowId, {
        tsEnd: window.ts,
        durationInSeconds: finalDuration
      });
    }
    const entity: DeepPartial<WindowActivityEntity> = {
      windowTitle: window.windowTitle,
      processName: window.process,
      processPath: window.processPath,
      processId: window.processId,
      url: window.url,
      activity: window.activity,
      tsStart: window.ts
    };
    const savedEntity = (await WindowActivityEntity.save(entity)) as WindowActivityEntity;
    this.prevWindowId = savedEntity.id;
    this.prevWindowTsStart = savedEntity.tsStart;
  }

  public static async finalizeCurrentWindow(): Promise<void> {
    if (this.prevWindowId && this.prevWindowTsStart) {
      const now = new Date();
      const duration = Math.floor((now.getTime() - this.prevWindowTsStart.getTime()) / 1000);
      const finalDuration = Math.min(duration, MAX_DURATION);
      await WindowActivityEntity.update(this.prevWindowId, {
        tsEnd: now,
        durationInSeconds: finalDuration
      });
      this.prevWindowId = null;
      this.prevWindowTsStart = null;
    }
  }

  public async getMostRecentWindowActivityDtos(itemCount: number): Promise<WindowActivityDto[]> {
    const items = await WindowActivityEntity.find({
      order: { createdAt: 'DESC' },
      take: itemCount
    });
    return items.map((item: WindowActivityEntity) => {
      return {
        windowTitle: item.windowTitle,
        processName: item.processName,
        processPath: item.processPath,
        processId: item.processId,
        url: item.url,
        activity: item.activity,
        tsStart: item.tsStart,
        tsEnd: item.tsEnd,
        durationInSeconds: item.durationInSeconds,
        id: item.id,
        createdAt: item.createdAt,
        updatedAt: item.updatedAt,
        deletedAt: item.deletedAt
      };
    });
  }

  public async obfuscateWindowActivityDtosById(ids: string[]): Promise<WindowActivityDto[]> {
    return (
      await WindowActivityEntity.find({
        where: {
          id: In([...ids])
        },
        order: { createdAt: 'DESC' }
      })
    ).map((activity) => {
      return {
        windowTitle: this.randomizeString(activity.windowTitle),
        url: this.randomizeUrl(activity.url),
        processName: activity.processName,
        processPath: activity.processPath,
        processId: activity.processId,
        activity: activity.activity,
        tsStart: activity.tsStart,
        tsEnd: activity.tsEnd,
        durationInSeconds: activity.durationInSeconds,
        id: activity.id,
        createdAt: activity.createdAt,
        updatedAt: activity.updatedAt,
        deletedAt: activity.deletedAt
      };
    });
  }

  public randomizeUrl(url: string): string {
    if (!url || url.length === 0) {
      return '';
    }
    const [splits, separators] = this.splitUrl(url);
    const max = Math.max(splits.length, separators.length);
    let out = '';
    let i = 0;
    while (i < max) {
      if (i < splits.length) {
        out += this.randomizeOrKeepEmpty(splits[i]);
      }
      if (i < separators.length) {
        out += separators[i];
      }
      i++;
    }
    return out;
  }

  public randomizeString(title: string): string {
    return this.randomizeOrKeepEmpty(title);
  }

  private splitUrl(url: string): [string[], string[]] {
    const seps = ['://', '/', '.', '?', '&', '=', '#', ':'];
    const splits = [];
    const separators = [];
    let str = '';
    let i = 0;
    while (i < url.length) {
      const char3 = url.substring(i, i + 3);
      const char = url[i];
      if (char3 == '://') {
        splits.push(str);
        str = '';
        separators.push(char3);
        i += 3;
      } else if (seps.includes(char)) {
        splits.push(str);
        str = '';
        separators.push(char);
        i++;
      } else {
        str += char;
        i++;
      }
    }
    splits.push(str);
    return [splits, separators];
  }

  private randomizeOrKeepEmpty(str: string): string {
    if (!str || str.length === 0) {
      return '';
    }
    if (this.randomStringMap.has(str)) {
      return this.randomStringMap.get(str);
    }
    const randomString = Math.random().toString(36).substring(2, 8);
    // making sure we don't have collisions
    if (this.randomStringMap.has(randomString)) {
      LOG.warn('[export] random string collision at map size', this.randomStringMap.size);
      return this.randomizeOrKeepEmpty(str);
    }
    // we have a new random string
    this.randomStringMap.set(str, randomString);
    return randomString;
  }
}
