/// Device settings screen — controls which native features Cognithor can access.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:provider/provider.dart';

import 'package:jarvis_ui/providers/connection_provider.dart';
import 'package:jarvis_ui/providers/device_provider.dart';
import 'package:jarvis_ui/theme/jarvis_theme.dart';

class DeviceSettingsScreen extends StatefulWidget {
  const DeviceSettingsScreen({super.key});

  @override
  State<DeviceSettingsScreen> createState() => _DeviceSettingsScreenState();
}

class _DeviceSettingsScreenState extends State<DeviceSettingsScreen> {
  final _serverUrlController = TextEditingController();
  bool _isCheckingConnection = false;

  @override
  void initState() {
    super.initState();
    final conn = context.read<ConnectionProvider>();
    _serverUrlController.text = conn.serverUrl;
  }

  @override
  void dispose() {
    _serverUrlController.dispose();
    super.dispose();
  }

  Future<void> _checkConnection() async {
    setState(() => _isCheckingConnection = true);
    final conn = context.read<ConnectionProvider>();
    await conn.setServerUrl(_serverUrlController.text.trim());
    if (mounted) setState(() => _isCheckingConnection = false);
  }

  Future<void> _togglePermission(
    DeviceProvider device,
    Permission permission,
    bool currentValue,
  ) async {
    if (kIsWeb) return;
    if (!currentValue) {
      await device.requestSinglePermission(permission);
    } else {
      // Toggling off: we can't revoke the OS permission but we stop sharing.
      device.disablePermission(permission);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final device = context.watch<DeviceProvider>();
    final conn = context.watch<ConnectionProvider>();

    return Scaffold(
      appBar: AppBar(title: const Text('Device Settings')),
      body: ListView(
        padding: const EdgeInsets.all(JarvisTheme.spacing),
        children: [
          // ----- Connection Status -----
          const _SectionHeader(title: 'Server Connection'),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(JarvisTheme.spacing),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        conn.state == JarvisConnectionState.connected
                            ? Icons.cloud_done
                            : Icons.cloud_off,
                        color: conn.state == JarvisConnectionState.connected
                            ? Colors.green
                            : Colors.red,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        conn.state == JarvisConnectionState.connected
                            ? 'Connected'
                            : conn.state == JarvisConnectionState.connecting
                                ? 'Connecting...'
                                : 'Disconnected',
                        style: theme.textTheme.bodyLarge,
                      ),
                    ],
                  ),
                  if (conn.backendVersion != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                        'Backend v${conn.backendVersion}',
                        style: theme.textTheme.bodySmall,
                      ),
                    ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _serverUrlController,
                    decoration: InputDecoration(
                      labelText: 'Server URL',
                      hintText: 'http://localhost:8741',
                      border: const OutlineInputBorder(),
                      suffixIcon: _isCheckingConnection
                          ? const Padding(
                              padding: EdgeInsets.all(12),
                              child: SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              ),
                            )
                          : IconButton(
                              icon: const Icon(Icons.refresh),
                              onPressed: _checkConnection,
                            ),
                    ),
                    onSubmitted: (_) => _checkConnection(),
                  ),
                  if (conn.errorMessage != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(
                        conn.errorMessage!,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colorScheme.error,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 24),

          // ----- Device Permissions -----
          if (!kIsWeb) ...[
            const _SectionHeader(title: 'Device Permissions'),
            Card(
              child: Column(
                children: [
                  _PermissionTile(
                    icon: Icons.location_on,
                    title: 'Location',
                    subtitle: device.lastPosition != null
                        ? '${device.lastPosition!.latitude.toStringAsFixed(4)}, '
                            '${device.lastPosition!.longitude.toStringAsFixed(4)}'
                        : 'Share location with Cognithor',
                    value: device.locationEnabled,
                    onChanged: (v) =>
                        _togglePermission(device, Permission.location, device.locationEnabled),
                  ),
                  _PermissionTile(
                    icon: Icons.camera_alt,
                    title: 'Camera',
                    subtitle: 'Allow Cognithor to use the camera',
                    value: device.cameraEnabled,
                    onChanged: (v) =>
                        _togglePermission(device, Permission.camera, device.cameraEnabled),
                  ),
                  _PermissionTile(
                    icon: Icons.mic,
                    title: 'Microphone',
                    subtitle: 'Allow voice commands',
                    value: device.microphoneEnabled,
                    onChanged: (v) =>
                        _togglePermission(device, Permission.microphone, device.microphoneEnabled),
                  ),
                  _PermissionTile(
                    icon: Icons.photo_library,
                    title: 'Photo Library',
                    subtitle: 'Allow access to photos',
                    value: device.photosEnabled,
                    onChanged: (v) =>
                        _togglePermission(device, Permission.photos, device.photosEnabled),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 24),

            // ----- Sensor Data -----
            const _SectionHeader(title: 'Sensor Data'),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(JarvisTheme.spacing),
                child: Column(
                  children: [
                    _InfoRow(
                      icon: Icons.battery_full,
                      label: 'Battery',
                      value: device.batteryLevel != null
                          ? '${device.batteryLevel}%'
                          : 'Unknown',
                    ),
                    _InfoRow(
                      icon: Icons.wifi,
                      label: 'Network',
                      value: device.networkType ?? 'Unknown',
                    ),
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.refresh),
                        label: const Text('Refresh Sensors'),
                        onPressed: () => device.refreshAll(),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Helper widgets
// ---------------------------------------------------------------------------

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title});
  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8, left: 4),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
      ),
    );
  }
}

class _PermissionTile extends StatelessWidget {
  const _PermissionTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return SwitchListTile(
      secondary: Icon(icon),
      title: Text(title),
      subtitle: Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis),
      value: value,
      onChanged: onChanged,
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icon, size: 20),
          const SizedBox(width: 12),
          Text(label, style: Theme.of(context).textTheme.bodyMedium),
          const Spacer(),
          Text(value, style: Theme.of(context).textTheme.bodyMedium),
        ],
      ),
    );
  }
}
