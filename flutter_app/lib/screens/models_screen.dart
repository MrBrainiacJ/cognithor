import 'package:flutter/material.dart';
import 'package:jarvis_ui/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';

import 'package:jarvis_ui/providers/admin_provider.dart';
import 'package:jarvis_ui/providers/config_provider.dart';
import 'package:jarvis_ui/providers/connection_provider.dart';
import 'package:jarvis_ui/theme/jarvis_theme.dart';
import 'package:jarvis_ui/widgets/neon_card.dart';
import 'package:jarvis_ui/widgets/jarvis_empty_state.dart';
import 'package:jarvis_ui/widgets/jarvis_section.dart';
import 'package:jarvis_ui/widgets/jarvis_stat.dart';
import 'package:jarvis_ui/widgets/jarvis_status_badge.dart';

/// Safely convert a model config value to Map.
/// API may return either a Map or a plain String (just the model name).
Map<String, dynamic> _asModelMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is String) return {'model': value};
  return {};
}

class ModelsScreen extends StatefulWidget {
  const ModelsScreen({super.key});

  @override
  State<ModelsScreen> createState() => _ModelsScreenState();
}

class _ModelsScreenState extends State<ModelsScreen> {
  bool _initialized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialized) {
      _initialized = true;
      _loadData();
    }
  }

  void _loadData() {
    final admin = context.read<AdminProvider>();
    final conn = context.read<ConnectionProvider>();
    admin.setApi(conn.api);
    admin.loadModels();
    admin.loadModelStats();
    // Also load config for configured model details
    final cfg = context.read<ConfigProvider>();
    cfg.setApi(conn.api);
    if (cfg.cfg.isEmpty) cfg.loadAll();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final admin = context.watch<AdminProvider>();

    if (admin.isLoading && admin.models == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            Text(l.loading),
          ],
        ),
      );
    }

    if (admin.error != null && admin.models == null) {
      return JarvisEmptyState(
        icon: Icons.model_training,
        title: l.modelsTitle,
        subtitle: admin.error,
        action: ElevatedButton.icon(
          onPressed: () {
            context.read<AdminProvider>().loadModels();
            context.read<AdminProvider>().loadModelStats();
          },
          icon: const Icon(Icons.refresh),
          label: Text(l.retry),
        ),
      );
    }

    final modelsData = admin.models ?? {};
    // Available models come as a flat list of strings from /models/available
    final rawAvailable = modelsData['models'];
    final available = rawAvailable is List ? rawAvailable : [];

    final stats = admin.modelStats ?? {};
    final totalModels = stats['total_models']?.toString() ?? available.length.toString();
    final providersList = stats['providers'];
    final providerCount = providersList is List ? providersList.length.toString() : '-';
    final capsList = stats['capabilities'];
    final capCount = capsList is List ? capsList.length.toString() : '-';

    // Configured models come from the config API (ConfigProvider)
    final cfg = context.watch<ConfigProvider>();
    final configModels = cfg.cfg['models'] as Map<String, dynamic>? ?? {};
    final planner = _asModelMap(configModels['planner']);
    final executor = _asModelMap(configModels['executor']);
    final coder = _asModelMap(configModels['coder']);
    final embedding = _asModelMap(configModels['embedding']);

    return RefreshIndicator(
      onRefresh: () async {
        final a = context.read<AdminProvider>();
        await Future.wait([a.loadModels(), a.loadModelStats()]);
      },
      color: JarvisTheme.accent,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Configured models
          JarvisSection(title: l.configured),
          _ConfiguredModelCard(
            label: l.plannerModel,
            icon: Icons.architecture,
            model: planner,
          ),
          _ConfiguredModelCard(
            label: l.executorModel,
            icon: Icons.play_arrow,
            model: executor,
          ),
          _ConfiguredModelCard(
            label: l.coderModel,
            icon: Icons.code,
            model: coder,
          ),
          _ConfiguredModelCard(
            label: l.embeddingModel,
            icon: Icons.text_fields,
            model: embedding,
          ),

          // Available models
          const SizedBox(height: 8),
          JarvisSection(title: l.availableModels),
          if (available.isEmpty)
            JarvisEmptyState(
              icon: Icons.model_training,
              title: l.noModels,
            ),
          ...available.map<Widget>((m) {
            // Available models may be strings or Maps
            final name = m is String ? m : (m is Map ? m['name']?.toString() ?? '' : m.toString());

            return Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: NeonCard(
                tint: JarvisTheme.sectionAdmin,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                child: Row(
                  children: [
                    Icon(Icons.model_training, size: 16, color: JarvisTheme.sectionAdmin),
                    const SizedBox(width: 10),
                    Expanded(child: Text(name, style: Theme.of(context).textTheme.bodyMedium)),
                  ],
                ),
              ),
            );
          }),
          // Remove the old caps/prov section — replace with a simple note
          if (available.length > 20) ...[
            const SizedBox(height: 8),
            Text(
              '${available.length} models available from ${cfg.cfg['llm_backend_type'] ?? 'backend'}',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: JarvisTheme.textSecondary),
            ),
          ],

          // Stats
          const SizedBox(height: 8),
          JarvisSection(title: l.modelStats),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              JarvisStat(
                label: l.total,
                value: totalModels,
                icon: Icons.model_training,
                color: JarvisTheme.accent,
              ),
              JarvisStat(
                label: l.providers,
                value: providerCount,
                icon: Icons.cloud,
                color: JarvisTheme.green,
              ),
              JarvisStat(
                label: l.capabilities,
                value: capCount,
                icon: Icons.star,
                color: JarvisTheme.orange,
              ),
            ],
          ),

          // Warnings (from model stats)
          if (stats['warnings'] is List && (stats['warnings'] as List).isNotEmpty) ...[
            const SizedBox(height: 16),
            JarvisSection(title: l.modelWarnings),
            ...(stats['warnings'] as List).map<Widget>((w) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: NeonCard(
                  tint: JarvisTheme.orange,
                  child: Row(
                    children: [
                      Icon(Icons.warning_amber, color: JarvisTheme.orange, size: 20),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          w.toString(),
                          style: TextStyle(color: JarvisTheme.orange, fontSize: 13),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }),
          ],
        ],
      ),
    );
  }
}

class _ConfiguredModelCard extends StatelessWidget {
  const _ConfiguredModelCard({
    required this.label,
    required this.icon,
    required this.model,
  });

  final String label;
  final IconData icon;
  final Map<String, dynamic> model;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final name = model['name']?.toString() ?? l.notConfigured;
    final provider = model['provider']?.toString() ?? '';

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: NeonCard(
        tint: JarvisTheme.sectionAdmin,
        glowOnHover: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 18, color: JarvisTheme.sectionAdmin),
                const SizedBox(width: 8),
                Expanded(child: Text(label, style: Theme.of(context).textTheme.titleMedium)),
                if (provider.isNotEmpty)
                  JarvisStatusBadge(label: provider, color: JarvisTheme.accent),
              ],
            ),
            const SizedBox(height: 4),
            Text(name, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ),
      ),
    );
  }
}
