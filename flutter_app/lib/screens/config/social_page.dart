import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:jarvis_ui/l10n/generated/app_localizations.dart';
import 'package:jarvis_ui/providers/config_provider.dart';
import 'package:jarvis_ui/widgets/form/form_widgets.dart';

class SocialPage extends StatelessWidget {
  const SocialPage({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Consumer<ConfigProvider>(
      builder: (context, cfg, _) {
        final social = cfg.cfg['social'] as Map<String, dynamic>? ?? {};
        final productName = (social['reddit_product_name'] ?? '').toString();
        final hasSubs = (social['reddit_subreddits'] as List<dynamic>?)?.isNotEmpty ?? false;
        final isConfigured = productName.isNotEmpty && hasSubs;

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (!isConfigured)
              Container(
                margin: const EdgeInsets.only(bottom: 16),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.orange.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.orange.withValues(alpha: 0.3)),
                ),
                child: Row(
                  children: [
                    Icon(Icons.warning_amber, color: Colors.orange[300], size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        l.socialSetupRequired,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Colors.orange[300],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            JarvisToggleField(
              label: l.autoScan,
              value: social['reddit_scan_enabled'] == true,
              onChanged: (v) => cfg.set('social.reddit_scan_enabled', v),
            ),
            JarvisTextField(
              label: l.productName,
              value: (social['reddit_product_name'] ?? '').toString(),
              placeholder: 'e.g. Cognithor',
              onChanged: (v) => cfg.set('social.reddit_product_name', v),
            ),
            JarvisTextField(
              label: l.productDescription,
              value: (social['reddit_product_description'] ?? '').toString(),
              placeholder: 'One-sentence description for AI scoring',
              onChanged: (v) =>
                  cfg.set('social.reddit_product_description', v),
            ),
            JarvisTextField(
              label: l.replyTone,
              value: (social['reddit_reply_tone'] ?? '').toString(),
              placeholder: 'helpful, technically credible, no sales pitch',
              onChanged: (v) => cfg.set('social.reddit_reply_tone', v),
            ),
            JarvisTextField(
              label: l.subreddits,
              value: (social['reddit_subreddits'] as List<dynamic>?)
                      ?.join(', ') ??
                  '',
              description: l.subredditsHint,
              placeholder: 'LocalLLaMA, SaaS, Python',
              onChanged: (v) => cfg.set(
                'social.reddit_subreddits',
                v
                    .split(',')
                    .map((s) => s.trim())
                    .where((s) => s.isNotEmpty)
                    .toList(),
              ),
            ),
            JarvisNumberField(
              label: l.minIntentScore,
              value: (social['reddit_min_score'] as num?) ?? 60,
              min: 0,
              max: 100,
              onChanged: (v) => cfg.set('social.reddit_min_score', v),
            ),
            JarvisNumberField(
              label: l.scanInterval,
              value: (social['reddit_scan_interval_minutes'] as num?) ?? 30,
              min: 5,
              max: 1440,
              onChanged: (v) =>
                  cfg.set('social.reddit_scan_interval_minutes', v),
            ),
            JarvisToggleField(
              label: l.autoPost,
              value: social['reddit_auto_post'] == true,
              description: l.autoPostHint,
              onChanged: (v) => cfg.set('social.reddit_auto_post', v),
            ),
          ],
        );
      },
    );
  }
}
