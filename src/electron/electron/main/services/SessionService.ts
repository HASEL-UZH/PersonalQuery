import { SessionEntity } from '../entities/SessionEntity';
import { UsageDataEntity } from '../entities/UsageDataEntity';
import { ExperienceSamplingResponseEntity } from '../entities/ExperienceSamplingResponseEntity';
import getMainLogger from '../../config/Logger';
import SessionDto from '../../../shared/dto/SessionDto';
import { LessThan } from 'typeorm';
import { UsageDataEventType } from '../../enums/UsageDataEventType.enum';

const LOG = getMainLogger('SessionService');

export class SessionService {
  public async createOrUpdateSessionFromEvent(
    type: UsageDataEventType,
    createdAt: Date
  ): Promise<void> {
    if (type === UsageDataEventType.ExperienceSamplingAnswered) {
      const priorAppStart = await UsageDataEntity.findOne({
        where: { type: UsageDataEventType.AppStart, createdAt: LessThan(createdAt) },
        order: { createdAt: 'DESC' }
      });

      const priorEsOpened = await ExperienceSamplingResponseEntity.findOne({
        where: { createdAt: LessThan(createdAt) },
        order: { createdAt: 'DESC' }
      });

      const priorStart =
        priorAppStart && priorEsOpened
          ? priorAppStart.createdAt > priorEsOpened.createdAt
            ? priorAppStart
            : priorEsOpened
          : priorAppStart || priorEsOpened;

      if (priorStart.createdAt >= createdAt) return;

      const duration = Math.floor((createdAt.getTime() - priorStart.createdAt.getTime()) / 1000);

      const esr = await ExperienceSamplingResponseEntity.findOne({
        where: { promptedAt: createdAt }
      });

      if (!esr) {
        LOG.warn(
          `No ES response found at ${createdAt.toISOString()}, creating session without response data`
        );
      } else {
        LOG.info(
          `Found ES response: "${esr.question}" (response=${esr.response}, skipped=${esr.skipped})`
        );
      }

      await SessionEntity.save({
        tsStart: priorStart.createdAt,
        tsEnd: createdAt,
        durationInSeconds: duration,
        question: esr?.question ?? null,
        scale: esr?.scale ?? null,
        response: esr?.response ?? null,
        skipped: esr?.skipped ?? null
      });
    }

    if (type === UsageDataEventType.AppQuit) {
      const priorStart = await UsageDataEntity.findOne({
        where: { type: UsageDataEventType.AppStart, createdAt: LessThan(createdAt) },
        order: { createdAt: 'DESC' }
      });

      if (!priorStart) {
        LOG.warn(`No prior session start found before ${createdAt.toISOString()}`);
        return;
      }

      if (priorStart.createdAt >= createdAt) {
        LOG.warn(
          `Invalid session range: priorStart=${priorStart.createdAt.toISOString()} >= createdAt=${createdAt.toISOString()}`
        );
        return;
      }

      const duration = Math.floor((createdAt.getTime() - priorStart.createdAt.getTime()) / 1000);
      LOG.info(
        `Creating session from ${priorStart.createdAt.toISOString()} to ${createdAt.toISOString()} (duration: ${duration}s)`
      );

      await SessionEntity.save({
        tsStart: stripMilliseconds(priorStart.createdAt),
        tsEnd: stripMilliseconds(createdAt),
        durationInSeconds: duration,
        question: null,
        scale: null,
        response: null,
        skipped: null
      });
    }
  }

  public async getMostRecentSessionDtos(count: number): Promise<SessionDto[]> {
    const sessions = await SessionEntity.find({
      order: { tsStart: 'DESC' },
      take: count
    });

    return sessions.map((s) => ({
      id: s.id,
      question: s.question,
      scale: s.scale,
      response: s.response,
      skipped: s.skipped,
      tsStart: s.tsStart,
      tsEnd: s.tsEnd,
      durationInSeconds: s.durationInSeconds
    }));
  }
}

function stripMilliseconds(date: Date): Date {
  const newDate = new Date(date);
  newDate.setMilliseconds(0);
  return newDate;
}
