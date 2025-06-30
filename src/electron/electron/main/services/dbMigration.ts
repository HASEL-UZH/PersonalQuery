import { parseISO, format } from 'date-fns';
import getMainLogger from '../../config/Logger';
import Database from 'better-sqlite3';

const LOG = getMainLogger('dbMigration');

export function updateSessionsFromUsageData(db: Database.Database): void {
  LOG.info('Creating session table if it does not exist...');
  db.prepare(
    `
    CREATE TABLE IF NOT EXISTS session (
      id TEXT PRIMARY KEY,
      tsStart datetime,
      tsEnd datetime,
      durationInSeconds INTEGER,
      question TEXT,
      scale INTEGER,
      response TEXT,
      skipped BOOLEAN
    )
  `
  ).run();

  LOG.info('Loading usage_data rows...');
  const usageRows = db
    .prepare(
      `
    SELECT id, created_at, type FROM usage_data
    WHERE type IN ('APP_START', 'EXPERIENCE_SAMPLING_AUTOMATICALLY_OPENED', 'APP_QUIT')
    ORDER BY created_at ASC
  `
    )
    .all();
  LOG.info(`Loaded ${usageRows.length} usage_data rows.`);

  LOG.info('Loading experience_sampling_responses rows...');
  const esrRaw = db
    .prepare(
      `
    SELECT id, promptedAt, question, scale, response, skipped
    FROM experience_sampling_responses
  `
    )
    .all();
  LOG.info(`Loaded ${esrRaw.length} experience_sampling_responses rows.`);

  const esrMap = new Map();
  for (const row of esrRaw) {
    const truncated = row.promptedAt.split('.')[0];
    esrMap.set(truncated, row);
  }

  const sessions = [];
  let currentStart = null;

  for (const row of usageRows) {
    const uid = row.id;
    const createdAt = row.created_at;
    const typ = row.type;

    if (typ === 'APP_START') {
      currentStart = createdAt;
    } else if (typ === 'EXPERIENCE_SAMPLING_AUTOMATICALLY_OPENED' && currentStart) {
      const startedDt = parseISO(currentStart);
      const endedDt = parseISO(createdAt);
      const duration = Math.floor((endedDt.getTime() - startedDt.getTime()) / 1000);

      const esr = esrMap.get(createdAt);
      let question = null,
        scale = null,
        response = null,
        skipped = null;

      if (esr) {
        question = esr.question;
        scale = esr.scale;
        response = esr.response;
        skipped = esr.skipped;

        if (
          question ===
          'Compared to your normal level of productivity, how productive do you consider the previous session?'
        ) {
          question = 'How productive was this session?';
        } else if (question === 'How well did you spend your time in the previous session?') {
          question = 'How well spent time?';
        }
      }

      sessions.push([
        uid,
        format(startedDt, 'yyyy-MM-dd HH:mm:ss.SSS'),
        format(endedDt, 'yyyy-MM-dd HH:mm:ss.SSS'),
        duration,
        question,
        scale,
        response,
        skipped
      ]);
      currentStart = createdAt;
    } else if (typ === 'APP_QUIT' && currentStart) {
      const startedDt = parseISO(currentStart);
      const endedDt = parseISO(createdAt);
      const duration = Math.floor((endedDt.getTime() - startedDt.getTime()) / 1000);

      sessions.push([
        uid,
        format(startedDt, 'yyyy-MM-dd HH:mm:ss.SSS'),
        format(endedDt, 'yyyy-MM-dd HH:mm:ss.SSS'),
        duration,
        null,
        null,
        null,
        null
      ]);
      currentStart = null;
    }
  }
  LOG.info(`Prepared ${sessions.length} session entries.`);

  const existingIdsRows = db.prepare(`SELECT id FROM session`).all();
  const existingIds = new Set(existingIdsRows.map((r) => r.id));
  LOG.info(`Found ${existingIds.size} existing sessions in DB.`);

  const insertStmt = db.prepare(
    `
    INSERT INTO session (
      id, tsStart, tsEnd, durationInSeconds,
      question, scale, response, skipped
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `
  );

  let insertedCount = 0;

  const insertTransaction = db.transaction(() => {
    for (const session of sessions) {
      if (existingIds.has(session[0])) continue;
      insertStmt.run(session);
      insertedCount++;
    }
  });
  insertTransaction();

  const deleteResult = db
    .prepare(
      `
    DELETE FROM session WHERE durationInSeconds IS NOT NULL AND durationInSeconds < 300
  `
    )
    .run();
  LOG.info(`Deleted short sessions (duration<300s): ${deleteResult.changes}`);
  LOG.info(`Inserted ${insertedCount} new sessions.`);
}

export function addWindowActivityDurations(db: Database.Database): void {
  const columns = db.prepare(`PRAGMA table_info(window_activity)`).all();
  const colNames = columns.map((c) => c.name);

  if (!colNames.includes('tsStart') && colNames.includes('ts')) {
    LOG.info(`Renaming column ts -> tsStart...`);
    db.prepare(`ALTER TABLE window_activity RENAME COLUMN ts TO tsStart`).run();
  }

  try {
    db.prepare(`ALTER TABLE window_activity ADD COLUMN durationInSeconds INTEGER`).run();
    LOG.info(`Added column durationInSeconds`);
  } catch {
    LOG.debug(`Column durationInSeconds already exists.`);
  }

  try {
    db.prepare(`ALTER TABLE window_activity ADD COLUMN tsEnd datetime`).run();
    LOG.info(`Added column tsEnd`);
  } catch {
    LOG.debug(`Column tsEnd already exists.`);
  }

  LOG.info(`Clearing computed fields...`);
  db.prepare(`UPDATE window_activity SET durationInSeconds = NULL, tsEnd = NULL`).run();

  const rows = db
    .prepare(
      `
    SELECT rowid, tsStart FROM window_activity ORDER BY tsStart ASC
  `
    )
    .all();
  LOG.info(`Loaded ${rows.length} window_activity rows.`);

  const appQuitsRaw = db
    .prepare(
      `
    SELECT created_at FROM usage_data WHERE type = 'APP_QUIT'
  `
    )
    .all();
  LOG.info(`Loaded ${appQuitsRaw.length} APP_QUIT events.`);

  const appQuitByDay = new Map<string, Date>();
  for (const { created_at } of appQuitsRaw) {
    const dt = parseISO(created_at);
    appQuitByDay.set(dt.toISOString().substring(0, 10), dt);
  }

  const updateStmt = db.prepare(
    `
    UPDATE window_activity
    SET durationInSeconds = ?, tsEnd = ?
    WHERE rowid = ?
  `
  );

  let updatedCount = 0;
  const updates = [];

  for (let i = 0; i < rows.length - 1; i++) {
    const { rowid, tsStart } = rows[i];
    const nextTs = rows[i + 1].tsStart;

    if (!tsStart || !nextTs) continue;

    const startDt = parseISO(tsStart);
    let endDt = parseISO(nextTs);

    if (startDt.toISOString().substring(0, 10) !== endDt.toISOString().substring(0, 10)) {
      const quitDt = appQuitByDay.get(startDt.toISOString().substring(0, 10));
      if (quitDt && startDt < quitDt && quitDt < endDt) {
        endDt = quitDt;
      }
    }

    const duration = Math.floor((endDt.getTime() - startDt.getTime()) / 1000);
    updates.push([duration, format(endDt, 'yyyy-MM-dd HH:mm:ss.SSS'), rowid]);
  }

  if (rows.length > 0) {
    const { rowid, tsStart } = rows[rows.length - 1];
    if (tsStart) {
      const startDt = parseISO(tsStart);
      const quitDt = appQuitByDay.get(startDt.toISOString().substring(0, 10));
      if (quitDt && quitDt > startDt) {
        const duration = Math.floor((quitDt.getTime() - startDt.getTime()) / 1000);
        updates.push([duration, format(quitDt, 'yyyy-MM-dd HH:mm:ss.SSS'), rowid]);
      }
    }
  }

  const updateTransaction = db.transaction(() => {
    for (const [duration, tsEnd, rowid] of updates) {
      updateStmt.run(duration, tsEnd, rowid);
      updatedCount++;
    }
  });
  updateTransaction();

  LOG.info(`Updated ${updatedCount} window_activity records.`);
}
