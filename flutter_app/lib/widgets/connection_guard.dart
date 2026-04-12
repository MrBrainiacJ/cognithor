import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:cognithor_ui/providers/connection_provider.dart';

/// Wraps child with a connection-lost overlay when backend is unreachable.
///
/// Only activates after the initial connection has been established
/// (i.e. [ConnectionProvider] was connected at least once). This avoids
/// conflicting with the SplashScreen which handles the first connect.
class ConnectionGuard extends StatelessWidget {
  final Widget child;
  const ConnectionGuard({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return Consumer<ConnectionProvider>(
      builder: (context, conn, _) {
        final showOverlay = conn.wasConnected &&
            (conn.state == JarvisConnectionState.error ||
                conn.state == JarvisConnectionState.disconnected);
        return Stack(
          children: [
            child,
            if (showOverlay)
              _ConnectionLostOverlay(
                state: conn.state,
                errorMessage: conn.errorMessage,
                onRetry: conn.connect,
              ),
          ],
        );
      },
    );
  }
}

class _ConnectionLostOverlay extends StatelessWidget {
  final JarvisConnectionState state;
  final String? errorMessage;
  final VoidCallback onRetry;

  const _ConnectionLostOverlay({
    required this.state,
    this.errorMessage,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      color: Colors.black.withValues(alpha: 0.7),
      child: Center(
        child: Card(
          elevation: 8,
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.cloud_off_rounded,
                  size: 64,
                  color: theme.colorScheme.error,
                ),
                const SizedBox(height: 16),
                Text(
                  'Backend nicht erreichbar',
                  style: theme.textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                Text(
                  errorMessage ?? 'Verbindung zum Server verloren',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color:
                        theme.colorScheme.onSurface.withValues(alpha: 0.7),
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                const SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                const SizedBox(height: 8),
                Text(
                  'Verbindung wird wiederhergestellt...',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color:
                        theme.colorScheme.onSurface.withValues(alpha: 0.5),
                  ),
                ),
                const SizedBox(height: 16),
                OutlinedButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Jetzt verbinden'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
