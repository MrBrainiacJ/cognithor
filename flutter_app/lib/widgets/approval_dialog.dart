import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:cognithor_ui/l10n/generated/app_localizations.dart';
import 'package:cognithor_ui/providers/chat_provider.dart';
import 'package:cognithor_ui/theme/jarvis_theme.dart';

class ApprovalDialog extends StatelessWidget {
  const ApprovalDialog({
    super.key,
    required this.request,
    required this.onRespond,
  });

  final ApprovalRequest request;
  final void Function(bool approved) onRespond;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);

    return Focus(
      autofocus: true,
      onKeyEvent: (node, event) {
        if (event is KeyDownEvent) {
          if (event.logicalKey == LogicalKeyboardKey.enter) {
            onRespond(true);
            return KeyEventResult.handled;
          }
          if (event.logicalKey == LogicalKeyboardKey.escape) {
            onRespond(false);
            return KeyEventResult.handled;
          }
        }
        return KeyEventResult.ignored;
      },
      child: Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: JarvisTheme.orange.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: JarvisTheme.orange.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(Icons.shield, color: JarvisTheme.orange, size: 20),
              const SizedBox(width: 8),
              Text(
                l.approvalTitle,
                style: TextStyle(
                  color: JarvisTheme.orange,
                  fontWeight: FontWeight.w600,
                  fontSize: 15,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            l.approvalBody(request.tool),
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Theme.of(context).cardColor,
              borderRadius: BorderRadius.circular(8),
            ),
            child: SelectableText(
              request.params.toString(),
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
              ),
            ),
          ),
          if (request.reason.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              l.approvalReason(request.reason),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              OutlinedButton(
                onPressed: () => onRespond(false),
                style: OutlinedButton.styleFrom(
                  foregroundColor: JarvisTheme.red,
                  side: BorderSide(color: JarvisTheme.red),
                ),
                child: Text(l.reject),
              ),
              const SizedBox(width: 8),
              ElevatedButton(
                onPressed: () => onRespond(true),
                style: ElevatedButton.styleFrom(
                  backgroundColor: JarvisTheme.green,
                ),
                child: Text(l.approve),
              ),
            ],
          ),
        ],
      ),
    ),
    );
  }
}
