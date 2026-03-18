import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import 'package:jarvis_ui/l10n/generated/app_localizations.dart';
import 'package:jarvis_ui/providers/config_provider.dart';
import 'package:jarvis_ui/providers/connection_provider.dart';
import 'package:jarvis_ui/theme/jarvis_theme.dart';
import 'package:jarvis_ui/widgets/jarvis_toast.dart';

import 'package:jarvis_ui/screens/config/general_page.dart';
import 'package:jarvis_ui/screens/config/language_page.dart';
import 'package:jarvis_ui/screens/config/providers_page.dart';
import 'package:jarvis_ui/screens/config/models_page.dart';
import 'package:jarvis_ui/screens/config/planner_page.dart';
import 'package:jarvis_ui/screens/config/executor_page.dart';
import 'package:jarvis_ui/screens/config/memory_page.dart';
import 'package:jarvis_ui/screens/config/channels_page.dart';
import 'package:jarvis_ui/screens/config/security_page.dart';
import 'package:jarvis_ui/screens/config/web_page.dart';
import 'package:jarvis_ui/screens/config/mcp_page.dart';
import 'package:jarvis_ui/screens/config/cron_page.dart';
import 'package:jarvis_ui/screens/config/database_page.dart';
import 'package:jarvis_ui/screens/config/logging_page.dart';
import 'package:jarvis_ui/screens/config/prompts_page.dart';
import 'package:jarvis_ui/screens/config/agents_page.dart';
import 'package:jarvis_ui/screens/config/bindings_page.dart';
import 'package:jarvis_ui/screens/config/system_page.dart';

class _PageDef {
  const _PageDef(this.icon, this.labelKey, this.key, this.builder);
  final IconData icon;
  final String Function(AppLocalizations l) labelKey;
  final String? key; // keyboard shortcut digit
  final Widget Function() builder;
}

final _pages = <_PageDef>[
  _PageDef(Icons.settings, (l) => l.configPageGeneral, '1', () => const GeneralPage()),
  _PageDef(Icons.language, (l) => l.configPageLanguage, '2', () => const LanguagePage()),
  _PageDef(Icons.cloud, (l) => l.configPageProviders, '3', () => const ProvidersPage()),
  _PageDef(Icons.model_training, (l) => l.configPageModels, '4', () => const ModelsPage()),
  _PageDef(Icons.architecture, (l) => l.configPagePlanner, '5', () => const PlannerPage()),
  _PageDef(Icons.play_arrow, (l) => l.configPageExecutor, '6', () => const ExecutorPage()),
  _PageDef(Icons.memory, (l) => l.configPageMemory, '7', () => const MemoryPage()),
  _PageDef(Icons.chat, (l) => l.configPageChannels, '8', () => const ChannelsPage()),
  _PageDef(Icons.shield, (l) => l.configPageSecurity, '9', () => const SecurityPage()),
  _PageDef(Icons.public, (l) => l.configPageWeb, '0', () => const WebPage()),
  _PageDef(Icons.dns, (l) => l.configPageMcp, null, () => const McpPage()),
  _PageDef(Icons.schedule, (l) => l.configPageCron, null, () => const CronPage()),
  _PageDef(Icons.storage, (l) => l.configPageDatabase, null, () => const DatabasePage()),
  _PageDef(Icons.article, (l) => l.configPageLogging, null, () => const LoggingPage()),
  _PageDef(Icons.edit_note, (l) => l.configPagePrompts, null, () => const PromptsPage()),
  _PageDef(Icons.smart_toy, (l) => l.configPageAgents, null, () => const AgentsConfigPage()),
  _PageDef(Icons.link, (l) => l.configPageBindings, null, () => const BindingsConfigPage()),
  _PageDef(Icons.build, (l) => l.configPageSystem, null, () => const SystemConfigPage()),
];

class ConfigScreen extends StatefulWidget {
  const ConfigScreen({super.key});

  @override
  State<ConfigScreen> createState() => _ConfigScreenState();
}

class _ConfigScreenState extends State<ConfigScreen> {
  int _selectedPage = 0;
  bool _initialized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialized) {
      _initialized = true;
      final cfg = context.read<ConfigProvider>();
      final conn = context.read<ConnectionProvider>();
      cfg.setApi(conn.api);
      // Only load if not already loaded (avoids reload on navigation back)
      if (cfg.cfg.isEmpty) {
        cfg.loadAll();
      }
    }
  }

  Future<void> _save() async {
    final cfg = context.read<ConfigProvider>();
    final l = AppLocalizations.of(context);
    final ok = await cfg.save();
    if (!mounted) return;
    if (cfg.sectionErrors.isNotEmpty) {
      final errSections = cfg.sectionErrors.keys.join(', ');
      JarvisToast.show(
        context,
        l.savedWithErrors(errSections),
        type: ToastType.warning,
      );
    } else {
      JarvisToast.show(
        context,
        ok ? l.configurationSaved : l.saveFailed,
        type: ok ? ToastType.success : ToastType.error,
      );
    }
  }

  void _navigateToPage(int index) {
    if (index >= 0 && index < _pages.length) {
      setState(() => _selectedPage = index);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final isWide = MediaQuery.sizeOf(context).width > 700;

    // Build keyboard shortcut bindings: Ctrl+1-9,0 for pages, Ctrl+S for save
    final bindings = <ShortcutActivator, VoidCallback>{
      const SingleActivator(LogicalKeyboardKey.keyS, control: true): _save,
    };
    // Ctrl+1 through Ctrl+9 for first 9 pages, Ctrl+0 for 10th
    final digitKeys = [
      LogicalKeyboardKey.digit1, LogicalKeyboardKey.digit2,
      LogicalKeyboardKey.digit3, LogicalKeyboardKey.digit4,
      LogicalKeyboardKey.digit5, LogicalKeyboardKey.digit6,
      LogicalKeyboardKey.digit7, LogicalKeyboardKey.digit8,
      LogicalKeyboardKey.digit9, LogicalKeyboardKey.digit0,
    ];
    for (var i = 0; i < digitKeys.length && i < _pages.length; i++) {
      final idx = i;
      bindings[SingleActivator(digitKeys[i], control: true)] =
          () => _navigateToPage(idx);
    }

    return CallbackShortcuts(
      bindings: bindings,
      child: Focus(
        autofocus: true,
        child: Scaffold(
          appBar: AppBar(
            title: Text(l.configTitle),
            actions: [
              // Reload button
              Consumer<ConfigProvider>(
                builder: (context, cfg, _) => IconButton(
                  icon: const Icon(Icons.refresh, size: 20),
                  tooltip: 'Reload config from backend',
                  onPressed: cfg.loading ? null : () => cfg.loadAll(),
                ),
              ),
            ],
          ),
          body: Consumer<ConfigProvider>(
            builder: (context, cfg, _) {
              if (cfg.loading && cfg.cfg.isEmpty) {
                return const Center(child: CircularProgressIndicator());
              }

              // Show error banner but still allow navigation if we have data
              return Column(
                children: [
                  // Error banner (non-blocking)
                  if (cfg.error != null)
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 8),
                      color: JarvisTheme.red.withValues(alpha: 0.15),
                      child: Row(
                        children: [
                          Icon(Icons.warning_amber,
                              size: 16, color: JarvisTheme.orange),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              cfg.error!,
                              style: TextStyle(
                                  color: JarvisTheme.orange, fontSize: 12),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          TextButton(
                            onPressed: () => cfg.loadAll(),
                            child: Text(l.retry, style: const TextStyle(fontSize: 12)),
                          ),
                        ],
                      ),
                    ),
                  // Main content
                  Expanded(
                    child: isWide
                        ? Row(
                            children: [
                              _buildSidebar(context, l),
                              const VerticalDivider(width: 1),
                              Expanded(child: _pages[_selectedPage].builder()),
                            ],
                          )
                        : Column(
                            children: [
                              _buildHorizontalNav(context, l),
                              Expanded(child: _pages[_selectedPage].builder()),
                            ],
                          ),
                  ),
                  // Save bar
                  _buildSaveBar(context, cfg, l),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildSidebar(BuildContext context, AppLocalizations l) {
    return SizedBox(
      width: 180,
      child: ListView.builder(
        itemCount: _pages.length,
        itemBuilder: (context, i) {
          final page = _pages[i];
          final selected = i == _selectedPage;
          return ListTile(
            dense: true,
            visualDensity: VisualDensity.compact,
            leading: Icon(page.icon,
                size: 18,
                color:
                    selected ? JarvisTheme.accent : JarvisTheme.textSecondary),
            title: Text(page.labelKey(l),
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                  color: selected
                      ? JarvisTheme.accent
                      : Theme.of(context).textTheme.bodyMedium?.color,
                )),
            trailing: page.key != null
                ? Text(
                    '^${page.key!}',
                    style: TextStyle(
                      fontSize: 10,
                      color: JarvisTheme.textTertiary,
                      fontFamily: 'monospace',
                    ),
                  )
                : null,
            selected: selected,
            selectedTileColor: JarvisTheme.accent.withValues(alpha: 0.08),
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            onTap: () => setState(() => _selectedPage = i),
          );
        },
      ),
    );
  }

  Widget _buildHorizontalNav(BuildContext context, AppLocalizations l) {
    return SizedBox(
      height: 48,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        itemCount: _pages.length,
        itemBuilder: (context, i) {
          final page = _pages[i];
          final selected = i == _selectedPage;
          return Padding(
            padding: const EdgeInsets.only(right: 4),
            child: ChoiceChip(
              label: Text(page.labelKey(l), style: const TextStyle(fontSize: 12)),
              avatar: Icon(page.icon, size: 14),
              selected: selected,
              onSelected: (_) => setState(() => _selectedPage = i),
              selectedColor: JarvisTheme.accent.withValues(alpha: 0.2),
            ),
          );
        },
      ),
    );
  }

  Widget _buildSaveBar(BuildContext context, ConfigProvider cfg, AppLocalizations l) {
    if (!cfg.hasChanges && !cfg.saving) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: JarvisTheme.surface,
        border: Border(top: BorderSide(color: JarvisTheme.border)),
      ),
      child: Row(
        children: [
          Icon(Icons.edit, size: 16, color: JarvisTheme.orange),
          const SizedBox(width: 8),
          Text(l.unsavedChanges),
          const Spacer(),
          TextButton(
            onPressed: cfg.saving ? null : () => cfg.discard(),
            child: Text(l.discard),
          ),
          const SizedBox(width: 8),
          ElevatedButton.icon(
            onPressed: cfg.saving ? null : _save,
            icon: cfg.saving
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.save, size: 16),
            label: Text(cfg.saving ? l.saving : l.saveCtrlS),
          ),
        ],
      ),
    );
  }
}
