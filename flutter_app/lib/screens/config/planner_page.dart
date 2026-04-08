import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:jarvis_ui/providers/config_provider.dart';
import 'package:jarvis_ui/widgets/form/form_widgets.dart';

class PlannerPage extends StatelessWidget {
  const PlannerPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<ConfigProvider>(
      builder: (context, cfg, _) {
        final planner =
            cfg.cfg['planner'] as Map<String, dynamic>? ?? {};
        final gk =
            cfg.cfg['gatekeeper'] as Map<String, dynamic>? ?? {};
        final sb =
            cfg.cfg['sandbox'] as Map<String, dynamic>? ?? {};

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            JarvisCollapsibleCard(
              title: 'Planner (PGE)',
              icon: Icons.architecture,
              initiallyExpanded: true,
              children: [
                JarvisNumberField(
                  label: 'Max Iterations',
                  value: (planner['max_iterations'] as num?) ?? 25,
                  onChanged: (v) => cfg.set('planner.max_iterations', v),
                  min: 1,
                  max: 50,
                ),
                JarvisNumberField(
                  label: 'Escalation After',
                  value: (planner['escalation_after'] as num?) ?? 3,
                  onChanged: (v) => cfg.set('planner.escalation_after', v),
                  min: 1,
                ),
                JarvisSliderField(
                  label: 'Temperature',
                  value:
                      (planner['temperature'] as num?)?.toDouble() ?? 0.7,
                  onChanged: (v) => cfg.set('planner.temperature', v),
                  max: 2.0,
                  step: 0.05,
                ),
                JarvisNumberField(
                  label: 'Response Token Budget',
                  value:
                      (planner['response_token_budget'] as num?) ?? 4000,
                  onChanged: (v) =>
                      cfg.set('planner.response_token_budget', v),
                  min: 256,
                  max: 128000,
                ),
              ],
            ),
            JarvisCollapsibleCard(
              title: 'Gatekeeper',
              icon: Icons.shield,
              children: [
                JarvisTextField(
                  label: 'Policies Directory',
                  value: (gk['policies_dir'] ?? '').toString(),
                  onChanged: (v) => cfg.set('gatekeeper.policies_dir', v),
                ),
                JarvisSelectField.fromStrings(
                  label: 'Default Risk Level',
                  value: (gk['default_risk_level'] ?? 'orange').toString(),
                  options: const ['green', 'yellow', 'orange', 'red'],
                  onChanged: (v) =>
                      cfg.set('gatekeeper.default_risk_level', v),
                ),
                JarvisNumberField(
                  label: 'Max Blocked Retries',
                  value: (gk['max_blocked_retries'] as num?) ?? 3,
                  onChanged: (v) =>
                      cfg.set('gatekeeper.max_blocked_retries', v),
                  min: 0,
                ),
              ],
            ),
            JarvisCollapsibleCard(
              title: 'Sandbox',
              icon: Icons.security,
              children: [
                JarvisSelectField.fromStrings(
                  label: 'Level',
                  value: (sb['level'] ?? 'process').toString(),
                  options: const [
                    'process', 'namespace', 'container', 'jobobject'
                  ],
                  onChanged: (v) => cfg.set('sandbox.level', v),
                ),
                JarvisNumberField(
                  label: 'Timeout (seconds)',
                  value: (sb['timeout_seconds'] as num?) ?? 30,
                  onChanged: (v) => cfg.set('sandbox.timeout_seconds', v),
                  min: 1,
                ),
                JarvisNumberField(
                  label: 'Max Memory (MB)',
                  value: (sb['max_memory_mb'] as num?) ?? 512,
                  onChanged: (v) => cfg.set('sandbox.max_memory_mb', v),
                  min: 64,
                ),
                JarvisNumberField(
                  label: 'Max CPU Seconds',
                  value: (sb['max_cpu_seconds'] as num?) ?? 30,
                  onChanged: (v) => cfg.set('sandbox.max_cpu_seconds', v),
                  min: 1,
                ),
                JarvisListField(
                  label: 'Allowed Paths',
                  value: _toStringList(sb['allowed_paths']),
                  onChanged: (v) => cfg.set('sandbox.allowed_paths', v),
                ),
                JarvisToggleField(
                  label: 'Network Access',
                  value: sb['network_access'] == true,
                  onChanged: (v) => cfg.set('sandbox.network_access', v),
                ),
                JarvisJsonEditor(
                  label: 'Environment Variables',
                  value: sb['env_vars'] ?? {},
                  onChanged: (v) => cfg.set('sandbox.env_vars', v),
                  rows: 4,
                ),
              ],
            ),
          ],
        );
      },
    );
  }

  static List<String> _toStringList(dynamic v) {
    if (v is List) return v.map((e) => e.toString()).toList();
    return [];
  }
}
