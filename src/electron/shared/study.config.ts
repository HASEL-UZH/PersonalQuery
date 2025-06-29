import { StudyConfiguration } from './StudyConfiguration';

const studyConfig: StudyConfiguration = {
  name: 'PersonalQuery Study',
  shortDescription:
    'PersonalQuery, an extension of the PersonalAnalytics tool that integrates an LLM to enable NL querying of personal activity data.',
  infoUrl: 'https://github.com/HASEL-UZH/PersonalQuery',
  privacyPolicyUrl:
    'https://github.com/HASEL-UZH/PersonalAnalytics/blob/dev-am/documentation/PRIVACY.md',
  uploadUrl: 'https://hasel.dev/upload',
  contactName: 'Kavishan Srirangarasa',
  contactEmail: 'kavishan.srirangarasa@uzh.ch',
  subjectIdLength: 6,
  dataExportEnabled: false,
  dataExportEncrypted: false,
  displayDaysParticipated: true,
  trackers: {
    windowActivityTracker: {
      enabled: true,
      intervalInMs: 1000,
      trackUrls: true,
      trackWindowTitles: true
    },
    userInputTracker: {
      enabled: true,
      intervalInMs: 10000
    },
    experienceSamplingTracker: {
      enabled: true,
      enabledWorkHours: true,
      scale: 7,
      questions: [
        'Compared to your normal level of productivity, how productive do you consider the previous session?',
        'How well did you spend your time in the previous session?'
      ],
      responseOptions: [
        ['not at all productive', 'moderately productive', 'very productive'],
        ['not well', 'moderately well', 'very well']
      ],
      intervalInMs: 1000 * 60 * 60 * 1,
      samplingRandomization: 0.2 // 20% randomization, so the interval will be between 48 and 72 minutes
    }
  }
};
export default studyConfig;
