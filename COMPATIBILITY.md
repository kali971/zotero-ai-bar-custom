# Compatibility

## Zotero version

The upstream manifest declares `strict_min_version: 6.999` and `strict_max_version: 11.*`. Treat this release as targeting Zotero 7 through Zotero 11.

## Operating systems

The XPI contains JavaScript, CSS, HTML and assets, without an OS-specific native binary. It is intended to run on platforms supported by the corresponding Zotero release. This custom build was verified on macOS; Windows and Linux installation is expected but was not separately tested in this release.

## API providers

Official providers follow the upstream plugin configuration. For a custom relay, configure the endpoint and model in Zotero yourself. The custom translation path avoids the structured `response_format` schema request and uses the ordinary streamed JSON-text path; the relay still needs to accept the request format required by the selected provider.

## Security

No user profile, API key, active provider configuration or Zotero `prefs.js` is included. Users must enter their own credentials after installation.

## Upgrade and rollback

Before replacing an existing installation, export or record your provider settings. To roll back, uninstall this custom build and install the upstream XPI again.
