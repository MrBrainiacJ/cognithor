import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:cognithor_ui/l10n/generated/app_localizations.dart';
import 'package:cognithor_ui/providers/config_provider.dart';
import 'package:cognithor_ui/theme/jarvis_theme.dart';
import 'package:cognithor_ui/widgets/form/form_widgets.dart';

class CronPage extends StatelessWidget {
  const CronPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<ConfigProvider>(
      builder: (context, cfg, _) {
        final hb = cfg.cfg['heartbeat'] as Map<String, dynamic>? ?? {};
        final plugins = cfg.cfg['plugins'] as Map<String, dynamic>? ?? {};

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            JarvisCollapsibleCard(
              title: 'Heartbeat',
              icon: Icons.favorite,
              initiallyExpanded: true,
              children: [
                JarvisToggleField(
                  label: 'Enabled',
                  value: hb['enabled'] == true,
                  onChanged: (v) => cfg.set('heartbeat.enabled', v),
                ),
                JarvisNumberField(
                  label: 'Interval (minutes)',
                  value: (hb['interval_minutes'] as num?) ?? 60,
                  onChanged: (v) => cfg.set('heartbeat.interval_minutes', v),
                  min: 1,
                ),
                JarvisTextField(
                  label: 'Checklist File',
                  value: (hb['checklist_file'] ?? '').toString(),
                  onChanged: (v) => cfg.set('heartbeat.checklist_file', v),
                ),
                JarvisTextField(
                  label: 'Channel',
                  value: (hb['channel'] ?? '').toString(),
                  onChanged: (v) => cfg.set('heartbeat.channel', v),
                ),
                JarvisTextField(
                  label: 'Model',
                  value: (hb['model'] ?? '').toString(),
                  onChanged: (v) => cfg.set('heartbeat.model', v),
                ),
              ],
            ),
            JarvisCollapsibleCard(
              title: 'Plugins',
              icon: Icons.extension,
              children: [
                JarvisTextField(
                  label: 'Skills Directory',
                  value: (plugins['skills_dir'] ?? '').toString(),
                  onChanged: (v) => cfg.set('plugins.skills_dir', v),
                ),
                JarvisToggleField(
                  label: 'Auto Update',
                  value: plugins['auto_update'] == true,
                  onChanged: (v) => cfg.set('plugins.auto_update', v),
                ),
              ],
            ),
            const Divider(height: 32),
            Row(
              children: [
                Text(AppLocalizations.of(context).cronJobs,
                    style: Theme.of(context)
                        .textTheme
                        .titleLarge
                        ?.copyWith(fontSize: 16)),
                const Spacer(),
                IconButton(
                  icon: Icon(Icons.add, color: JarvisTheme.accent),
                  onPressed: () => cfg.addCronJob({
                    'name': 'new-job',
                    'schedule': '0 * * * *',
                    'command': '',
                    'enabled': true,
                  }),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ...List.generate(cfg.cronJobs.length, (i) {
              final job = cfg.cronJobs[i];
              return JarvisCollapsibleCard(
                title: (job['name'] ?? 'Job $i').toString(),
                icon: Icons.schedule,
                badge: _humanCron(job['schedule']?.toString() ?? ''),
                children: [
                  JarvisTextField(
                    label: 'Name',
                    value: (job['name'] ?? '').toString(),
                    onChanged: (v) => cfg.updateCronJob(
                        i, {...job, 'name': v}),
                  ),
                  JarvisTextField(
                    label: 'Schedule (cron)',
                    value: (job['schedule'] ?? '').toString(),
                    onChanged: (v) => cfg.updateCronJob(
                        i, {...job, 'schedule': v}),
                    mono: true,
                  ),
                  JarvisTextField(
                    label: 'Command',
                    value: (job['command'] ?? '').toString(),
                    onChanged: (v) => cfg.updateCronJob(
                        i, {...job, 'command': v}),
                  ),
                  JarvisToggleField(
                    label: 'Enabled',
                    value: job['enabled'] == true,
                    onChanged: (v) => cfg.updateCronJob(
                        i, {...job, 'enabled': v}),
                  ),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton.icon(
                      onPressed: () => cfg.removeCronJob(i),
                      icon: Icon(Icons.delete,
                          size: 16, color: JarvisTheme.red),
                      label: Text(AppLocalizations.of(context).remove,
                          style: TextStyle(color: JarvisTheme.red)),
                    ),
                  ),
                ],
              );
            }),
          ],
        );
      },
    );
  }

  static String _humanCron(String cron) {
    if (cron.isEmpty) return '';
    final parts = cron.split(' ');
    if (parts.length < 5) return cron;
    final min = parts[0];
    final hour = parts[1];
    if (min != '*' && hour != '*') {
      return 'at ${hour.padLeft(2, '0')}:${min.padLeft(2, '0')}';
    }
    if (min == '0' && hour == '*') return 'every hour';
    if (min == '*') return 'every minute';
    return cron;
  }
}
