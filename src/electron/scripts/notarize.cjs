const { notarize } = require('@electron/notarize');
const { execSync } = require('child_process');

exports.default = async function afterSign(context) {
  const { electronPlatformName, appOutDir, packager } = context;

  if (electronPlatformName === 'darwin') {
    console.info('Starting notarization step.');

    if (!process.env.CI) {
      console.warn('Skipping notarizing step. Packaging is not running in CI');
      return;
    }

    if (!('APPLE_ID' in process.env && 'APPLE_APP_SPECIFIC_PASSWORD' in process.env)) {
      console.warn(
        'Skipping notarizing step. APPLE_ID and APPLE_APP_SPECIFIC_PASSWORD env variables must be set'
      );
      return;
    }

    const appName = packager.appInfo.productFilename;

    await notarize({
      tool: 'notarytool',
      appPath: `${appOutDir}/${appName}.app`,
      appleId: process.env.APPLE_ID,
      appleIdPassword: process.env.APPLE_APP_SPECIFIC_PASSWORD,
      teamId: process.env.APPLE_TEAM_ID
    });
  }

  if (electronPlatformName === 'win32') {
    const exePath = `${appOutDir}\\${packager.appInfo.productFilename}.exe`;
    const command =
      `pwsh.exe -NoProfile -NonInteractive -Command ` +
      `Invoke-TrustedSigning ` +
      `-Endpoint '${process.env.AZURE_ENDPOINT}' ` +
      `-CertificateProfileName '${process.env.AZURE_CERT_PROFILE_NAME}' ` +
      `-CodeSigningAccountName '${process.env.AZURE_CODE_SIGNING_NAME}' ` +
      `-PublisherName '${process.env.AZURE_PUBLISHER_NAME}' ` +
      `-TimestampRfc3161 'http://timestamp.acs.microsoft.com' ` +
      `-TimestampDigest 'SHA256' ` +
      `-FileDigest 'SHA256' ` +
      `-Files "${exePath}"`;

    console.info(`Signing Windows executable with Azure Trusted Signing: ${exePath}`);
    execSync(command, { stdio: 'inherit' });
  }
};
