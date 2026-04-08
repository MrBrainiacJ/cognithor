/// QR Scanner screen — scans pairing QR codes from the Cognithor server.
///
/// Uses the device camera (via mobile_scanner package) on native platforms.
/// On web, shows a text input fallback for pasting the QR payload.
library;

import 'dart:convert';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:jarvis_ui/l10n/generated/app_localizations.dart';
import 'package:jarvis_ui/providers/connection_provider.dart';
import 'package:jarvis_ui/theme/jarvis_theme.dart';
import 'package:jarvis_ui/widgets/neon_card.dart';

class QrScannerScreen extends StatefulWidget {
  const QrScannerScreen({super.key});

  @override
  State<QrScannerScreen> createState() => _QrScannerScreenState();
}

class _QrScannerScreenState extends State<QrScannerScreen> {
  final _pasteController = TextEditingController();
  bool _processing = false;
  String? _error;
  bool _success = false;

  @override
  void dispose() {
    _pasteController.dispose();
    super.dispose();
  }

  Future<void> _processQrPayload(String payload) async {
    if (payload.trim().isEmpty) return;

    setState(() {
      _processing = true;
      _error = null;
    });

    try {
      // Parse the QR payload (JSON with server_url and token)
      final data = jsonDecode(payload) as Map<String, dynamic>;
      final serverUrl = data['server_url'] as String?;
      final token = data['token'] as String?;

      if (serverUrl == null || token == null) {
        throw const FormatException('Invalid QR payload: missing server_url or token');
      }

      // Connect to the server
      final conn = context.read<ConnectionProvider>();
      await conn.setServerUrl(serverUrl);

      // Verify connection works with the token
      final api = conn.api;
      final health = await api.get('/health');
      if (health.containsKey('error')) {
        throw Exception(health['error']);
      }

      setState(() {
        _success = true;
        _processing = false;
      });

      // Pop back after short delay
      if (mounted) {
        await Future.delayed(const Duration(seconds: 2));
        if (mounted) Navigator.of(context).pop(true);
      }
    } on FormatException {
      setState(() {
        _error = AppLocalizations.of(context).qrScanError;
        _processing = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _processing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(l.scanQrCode)),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Status icon
            Icon(
              _success
                  ? Icons.check_circle
                  : _error != null
                      ? Icons.error
                      : Icons.qr_code_scanner,
              size: 80,
              color: _success
                  ? Colors.green
                  : _error != null
                      ? Colors.red
                      : JarvisTheme.accent,
            ),
            const SizedBox(height: 24),

            // Status text
            Text(
              _success
                  ? l.pairingSuccess
                  : _error ?? l.scanQrHint,
              style: theme.textTheme.titleMedium?.copyWith(
                color: _error != null ? Colors.red : null,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),

            if (!_success) ...[
              if (kIsWeb) ...[
                // Web fallback: paste QR payload
                Text(
                  'Paste the QR payload from the server:',
                  style: theme.textTheme.bodySmall,
                ),
                const SizedBox(height: 12),
              ],

              // Camera scanner placeholder + paste input
              NeonCard(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      if (!kIsWeb) ...[
                        // Native: camera area placeholder
                        // TODO: Add mobile_scanner dependency for real camera scanning
                        Container(
                          height: 250,
                          decoration: BoxDecoration(
                            color: Colors.black12,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: JarvisTheme.accent.withValues(alpha: 0.3),
                            ),
                          ),
                          child: const Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.camera_alt, size: 48, color: Colors.grey),
                                SizedBox(height: 8),
                                Text(
                                  'Camera scanner\n(add mobile_scanner to pubspec.yaml)',
                                  textAlign: TextAlign.center,
                                  style: TextStyle(color: Colors.grey),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),
                        const Divider(),
                        const SizedBox(height: 8),
                        Text(
                          'Or paste the QR payload:',
                          style: theme.textTheme.bodySmall,
                        ),
                        const SizedBox(height: 8),
                      ],

                      // Paste input (works on all platforms)
                      TextField(
                        controller: _pasteController,
                        maxLines: 4,
                        decoration: InputDecoration(
                          hintText: '{"server_url": "...", "token": "..."}',
                          border: const OutlineInputBorder(),
                          suffixIcon: IconButton(
                            icon: const Icon(Icons.send),
                            onPressed: _processing
                                ? null
                                : () => _processQrPayload(_pasteController.text),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton(
                          onPressed: _processing
                              ? null
                              : () => _processQrPayload(_pasteController.text),
                          child: _processing
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              : Text(l.send),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
