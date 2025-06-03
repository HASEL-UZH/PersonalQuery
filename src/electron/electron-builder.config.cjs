module.exports = {
  productName: 'PersonalQuery',
  appId: 'ch.ifi.hasel.personalquery',
  asar: true,
  asarUnpack: [
    'node_modules/better_sqlite3/**',
    'node_modules/sqlite3/**',
    'node_modules/**/*.node',
    'pq-backend.exe'
  ],
  directories: {
    output: 'release/${version}'
  },
  files: [
    'dist',
    'dist-electron',
    {
      from: '../py-backend/dist/pq-backend.exe',
      to: 'pq-backend.exe'
    },
    '!node_modules/uiohook-napi/build/**'
  ],
  extraResources: [
    {
      from: '../py-backend/dist/pq-backend.exe',
      to: 'pq-backend.exe',
      filter: ['**/*']
    }
  ],
  publish: {
    provider: 'github',
    owner: 'kauii',
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
    artifactName: '${productName}-${version}-Windows.${ext}',
    azureSignOptions: {
      publisherName: `${process.env.AZURE_PUBLISHER_NAME}`,
      endpoint: `${process.env.AZURE_ENDPOINT}`,
      codeSigningAccountName: `${process.env.AZURE_CODE_SIGNING_NAME}`,
      certificateProfileName: `${process.env.AZURE_CERT_PROFILE_NAME}`
    }
  },
  nsis: {
    oneClick: true,
    deleteAppDataOnUninstall: false,
    differentialPackage: false,
    artifactName: '${productName}-${version}-Windows.${ext}'
  }
};
