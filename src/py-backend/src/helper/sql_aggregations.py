from schemas import AggregationFeature

aggregation_sql_templates = [
    {
        "feature": AggregationFeature.context_switch,
        "sql_template": """
SELECT 
  prev_activity || ' → ' || activity AS switch_type,
  COUNT(*) AS switch_count
FROM (
  SELECT ts, activity,
         LAG(activity) OVER (ORDER BY ts) AS prev_activity
  FROM window_activity
  WHERE {time_filter}
)
WHERE activity != prev_activity
GROUP BY switch_type
ORDER BY switch_count DESC;
""".strip()
    },
    {
        "feature": AggregationFeature.total_focus_time,
        "sql_template": """
SELECT 
  activity,
  processName,
  windowTitle,
  SUM(durationInSeconds) AS total_focus_time
FROM window_activity
WHERE {time_filter}
GROUP BY activity, processName, windowTitle
ORDER BY total_focus_time DESC;
""".strip()
    },
    {
        "feature": AggregationFeature.category_buckets,
        "sql_template": """
SELECT 
  activity AS category,
  SUM(durationInSeconds) AS total_time
FROM window_activity
WHERE {time_filter}
GROUP BY activity
ORDER BY total_time DESC;
""".strip()
    },
    {
        "feature": AggregationFeature.input_activity_volume,
        "sql_template": """
SELECT
  SUM(keysTotal) AS total_keystrokes,
  SUM(clickTotal) AS total_clicks,
  ROUND(SUM(movedDistance), 2) AS total_mouse_movement,
  ROUND(SUM(scrollDelta), 2) AS total_scroll
FROM user_input
WHERE {time_filter};
""".strip()
    },
    {
        "feature": AggregationFeature.typing_streaks,
        "sql_template": """
SELECT COUNT(*) AS typing_streaks
FROM (
    SELECT 
      tsStart,
      LAG(tsEnd) OVER (ORDER BY tsStart) AS prev_end
    FROM user_input
    WHERE {time_filter}
      AND keysTotal > 0
)
WHERE strftime('%s', tsStart) - strftime('%s', prev_end) > 60;
""".strip()
    },
    {
        "feature": AggregationFeature.typing_gaps,
        "sql_template": """
SELECT COUNT(*) AS typing_gaps
FROM (
    SELECT 
      tsStart,
      LAG(tsEnd) OVER (ORDER BY tsStart) AS prev_end
    FROM user_input
    WHERE {time_filter}
      AND keysTotal > 0
)
WHERE strftime('%s', tsStart) - strftime('%s', prev_end) >= 300;
""".strip()
    },
    {
        "feature": AggregationFeature.user_input_by_app,
        "sql_template": """
SELECT 
  w.activity,
  w.processName,
  SUM(u.keysTotal) AS total_keystrokes,
  SUM(u.clickTotal) AS total_clicks,
  ROUND(SUM(u.movedDistance), 2) AS total_mouse_movement,
  ROUND(SUM(u.scrollDelta), 2) AS total_scroll
FROM user_input u
JOIN window_activity w 
  ON u.tsStart BETWEEN w.ts AND w.tsEnd
WHERE {time_filter}
GROUP BY w.activity, w.processName
ORDER BY total_keystrokes DESC;
""".strip()
    },
    {
        "feature": AggregationFeature.typing_density,
        "sql_template": """
SELECT 
  ROUND(
    SUM(keysTotal) * 1.0 / 
    ((julianday(MAX(tsEnd)) - julianday(MIN(tsStart))) * 86400),
    2
  ) AS typing_density_per_second
FROM user_input
WHERE {time_filter}
  AND keysTotal > 0;
""".strip()
    },
    {
        "feature": AggregationFeature.activity_category_ratio,
        "sql_template": """
SELECT 
  ROUND(
    SUM(CASE 
          WHEN activity IN ({category_list}) THEN durationInSeconds 
          ELSE 0 
        END) * 1.0 /
    SUM(durationInSeconds),
    2
  ) AS category_time_ratio
FROM window_activity
WHERE {time_filter};
""".strip()
    },
    {
        "feature": AggregationFeature.typing_productivity,
        "sql_template": """
SELECT 
  ROUND(
    SUM(u.keysTotal) * 1.0 / 
    SUM(w.durationInSeconds), 
    2
  ) AS typing_productivity
FROM user_input u
JOIN window_activity w 
  ON u.tsStart >= w.ts 
  AND u.tsStart < datetime(w.ts, '+' || w.durationInSeconds || ' seconds')
WHERE {time_filter}
  AND u.keysTotal > 0
  AND w.activity IN ('WorkRelatedBrowinsg','DevCode', 'DevVc', 'GenerativeAI');

""".strip()
    }
]


