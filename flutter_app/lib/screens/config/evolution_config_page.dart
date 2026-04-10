import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:jarvis_ui/providers/config_provider.dart';
import 'package:jarvis_ui/theme/jarvis_theme.dart';

class EvolutionConfigPage extends StatelessWidget {
  const EvolutionConfigPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<ConfigProvider>(
      builder: (context, cfg, _) {
        final evo = cfg.cfg['evolution'] as Map<String, dynamic>? ?? {};
        final enabled = evo['enabled'] == true;
        final idleThreshold = ((evo['idle_threshold_seconds'] as num?) ?? 300).toInt();
        final maxCycles = ((evo['max_cycles_per_day'] as num?) ?? 10).toInt();
        final llmEnabled = evo['llm_enabled'] == true;

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Evolution Engine Toggle
            SwitchListTile(
              title: const Text('Evolution Engine'),
              subtitle: const Text('Enable autonomous learning during idle time'),
              value: enabled,
              activeColor: JarvisTheme.accent,
              onChanged: (v) => cfg.set('evolution.enabled', v),
            ),
            const Divider(height: 24),

            // Idle Threshold
            ListTile(
              title: const Text('Idle Threshold'),
              subtitle: Text('Start learning after $idleThreshold seconds of inactivity'),
              trailing: SizedBox(
                width: 120,
                child: DropdownButtonFormField<int>(
                  value: [60, 120, 300, 600, 900, 1800].contains(idleThreshold) ? idleThreshold : 300,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  items: const [
                    DropdownMenuItem(value: 60, child: Text('1 min')),
                    DropdownMenuItem(value: 120, child: Text('2 min')),
                    DropdownMenuItem(value: 300, child: Text('5 min')),
                    DropdownMenuItem(value: 600, child: Text('10 min')),
                    DropdownMenuItem(value: 900, child: Text('15 min')),
                    DropdownMenuItem(value: 1800, child: Text('30 min')),
                  ],
                  onChanged: (v) => cfg.set('evolution.idle_threshold_seconds', v),
                ),
              ),
            ),
            const SizedBox(height: 12),

            // Max Cycles per Day
            ListTile(
              title: const Text('Max Cycles / Day'),
              subtitle: Text('$maxCycles cycles allowed per day'),
              trailing: SizedBox(
                width: 120,
                child: DropdownButtonFormField<int>(
                  value: [1, 3, 5, 10, 20, 50].contains(maxCycles) ? maxCycles : 10,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  items: const [
                    DropdownMenuItem(value: 1, child: Text('1')),
                    DropdownMenuItem(value: 3, child: Text('3')),
                    DropdownMenuItem(value: 5, child: Text('5')),
                    DropdownMenuItem(value: 10, child: Text('10')),
                    DropdownMenuItem(value: 20, child: Text('20')),
                    DropdownMenuItem(value: 50, child: Text('50')),
                  ],
                  onChanged: (v) => cfg.set('evolution.max_cycles_per_day', v),
                ),
              ),
            ),
            const SizedBox(height: 12),

            // LLM Enabled
            SwitchListTile(
              title: const Text('LLM-powered Learning'),
              subtitle: const Text('Use LLM for research (costs tokens). Disable for memory-only mode.'),
              value: llmEnabled,
              activeColor: JarvisTheme.accent,
              onChanged: (v) => cfg.set('evolution.llm_enabled', v),
            ),
          ],
        );
      },
    );
  }
}
