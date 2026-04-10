import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:cognithor_ui/l10n/generated/app_localizations.dart';
import 'package:cognithor_ui/providers/config_provider.dart';
import 'package:cognithor_ui/widgets/form/form_widgets.dart';

class GeneralPage extends StatelessWidget {
  const GeneralPage({super.key});

  /// Resolve version from config first, then from backend health check.
  String _resolveVersion(ConfigProvider cfg) {
    final cfgVersion = cfg.cfg['version']?.toString();
    if (cfgVersion != null && cfgVersion.isNotEmpty && cfgVersion != '-') {
      return cfgVersion;
    }
    return 'Unknown';
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Consumer<ConfigProvider>(
      builder: (context, cfg, _) {
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            JarvisTextField(
              label: l.fieldOwnerName,
              value: (cfg.cfg['owner_name'] ?? '').toString(),
              onChanged: (v) => cfg.set('owner_name', v),
            ),
            JarvisSelectField.fromStrings(
              label: l.fieldOperationMode,
              description: l.operationModeDesc,
              value: (cfg.cfg['operation_mode'] ?? 'auto').toString(),
              options: const ['auto', 'offline', 'online', 'hybrid'],
              onChanged: (v) => cfg.set('operation_mode', v),
            ),
            JarvisReadOnlyField(
              label: l.backendVersion,
              value: _resolveVersion(cfg),
            ),
            JarvisToggleField(
              label: l.fieldCostTracking,
              description: 'Track LLM API costs',
              value: cfg.cfg['cost_tracking_enabled'] == true,
              onChanged: (v) => cfg.set('cost_tracking_enabled', v),
            ),
            if (cfg.cfg['cost_tracking_enabled'] == true) ...[
              JarvisNumberField(
                label: l.fieldDailyBudget,
                value: (cfg.cfg['daily_budget_usd'] as num?) ?? 0,
                onChanged: (v) => cfg.set('daily_budget_usd', v),
                min: 0,
                decimal: true,
              ),
              JarvisNumberField(
                label: l.fieldMonthlyBudget,
                value: (cfg.cfg['monthly_budget_usd'] as num?) ?? 0,
                onChanged: (v) => cfg.set('monthly_budget_usd', v),
                min: 0,
                decimal: true,
              ),
            ],
          ],
        );
      },
    );
  }
}
