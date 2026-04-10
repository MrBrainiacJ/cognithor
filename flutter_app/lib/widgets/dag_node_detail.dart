import 'package:flutter/material.dart';
import 'package:cognithor_ui/theme/jarvis_theme.dart';

/// Detail panel shown when a DAG node is tapped.
class DagNodeDetail extends StatelessWidget {
  const DagNodeDetail({
    super.key,
    required this.nodeData,
    this.onClose,
  });

  final Map<String, dynamic> nodeData;
  final VoidCallback? onClose;

  @override
  Widget build(BuildContext context) {
    final status = (nodeData['status'] ?? 'unknown').toString();
    final duration = nodeData['duration_ms'] ?? 0;
    final output = (nodeData['output'] ?? '').toString();
    final error = (nodeData['error'] ?? '').toString();
    final retries = nodeData['retry_count'] ?? 0;

    return Container(
      width: 320,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: JarvisTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: JarvisTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              _statusIcon(status),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  (nodeData['name'] ?? nodeData['id'] ?? 'Node').toString(),
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                ),
              ),
              if (onClose != null)
                IconButton(
                  icon: const Icon(Icons.close, size: 16),
                  onPressed: onClose,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),
            ],
          ),
          const SizedBox(height: 12),
          _row('Status', status),
          _row('Duration', '${duration}ms'),
          if (retries is int && retries > 0) _row('Retries', '$retries'),
          if (nodeData['type'] != null) _row('Type', nodeData['type'].toString()),
          if (nodeData['tool_name'] != null)
            _row('Tool', nodeData['tool_name'].toString()),
          if (output.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text('Output:',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Container(
              constraints: const BoxConstraints(maxHeight: 120),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.black26,
                borderRadius: BorderRadius.circular(6),
              ),
              child: SingleChildScrollView(
                child: Text(
                  output.length > 500
                      ? '${output.substring(0, 500)}...'
                      : output,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                ),
              ),
            ),
          ],
          if (error.isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: JarvisTheme.red.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(6),
                border:
                    Border.all(color: JarvisTheme.red.withValues(alpha: 0.3)),
              ),
              child: Text(
                error,
                style: TextStyle(color: JarvisTheme.red, fontSize: 11),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: [
          SizedBox(
            width: 70,
            child: Text(label,
                style:
                    TextStyle(fontSize: 11, color: JarvisTheme.textSecondary)),
          ),
          Expanded(child: Text(value, style: const TextStyle(fontSize: 11))),
        ],
      ),
    );
  }

  Widget _statusIcon(String status) {
    final (IconData icon, Color color) = switch (status.toLowerCase()) {
      'running' => (Icons.play_circle, JarvisTheme.accent),
      'complete' || 'done' || 'success' => (Icons.check_circle, JarvisTheme.green),
      'error' || 'failure' => (Icons.error, JarvisTheme.red),
      'skipped' => (Icons.skip_next, JarvisTheme.textSecondary),
      _ => (Icons.pending, JarvisTheme.textTertiary),
    };
    return Icon(icon, size: 18, color: color);
  }
}
