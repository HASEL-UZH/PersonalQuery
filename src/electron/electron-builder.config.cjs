const backendFile = process.platform === 'win32' ? 'pq-backend.exe' : 'pq-backend';

module.exports = {
  productName: 'PersonalQuery',
  appId: 'ch.ifi.hasel.personalquery',
  asar: true,
  asarUnpack: [
    'node_modules/better_sqlite3/**',
    'node_modules/sqlite3/**',
    'node_modules/**/*.node',
    backendFile
  ],
  directories: {
    output: 'release/${version}'
  },
  files: [
    'dist',
    'dist-electron',
    {
      from: `../py-backend/dist/${backendFile}`,
      to: backendFile
    },
    '!node_modules/uiohook-napi/build/**'
  ],
  extraResources: [
    {
      from: `../py-backend/dist/${backendFile}`,
      to: backendFile,
      filter: ['**/*']
    }
  ],
  publish: {
    provider: 'github',
    owner: 'HASEL-UZH',
    repo: 'PersonalQuery'
  },
  afterSign: 'scripts/notarize.cjs',
  mac: {
    artifactName: '${productName}-${version}-${arch}.${ext}',
    entitlements: 'build/entitlements.mac.plist',
    entitlementsInherit: 'build/entitlements.mac.plist',
    hardenedRuntime: true,
    gatekeeperAssess: false,
    notarize: false,
    extendInfo: [
      {
        key: 'NSAppleEventsUsageDescription',
        value: 'Please allow access to use the application.'
      },
      {
        key: 'NSDocumentsFolderUsageDescription',
        value: 'Please allow access to use the application.'
      },
      {
        key: 'NSDownloadsFolderUsageDescription',
        value: 'Please allow access to use the application.'
      }
    ]
  },
  dmg: {
    writeUpdateInfo: false
  },
  win: {
    target: ['nsis'],
    verifyUpdateCodeSignature: false,
    artifactName: '${productName}-${version}-Windows.${ext}'
  },
  nsis: {
    oneClick: true,
    deleteAppDataOnUninstall: false,
    differentialPackage: false,
    artifactName: '${productName}-${version}-Windows.${ext}'
  }
};
