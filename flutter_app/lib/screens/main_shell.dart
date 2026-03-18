import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:jarvis_ui/l10n/generated/app_localizations.dart';
import 'package:jarvis_ui/providers/theme_provider.dart';
import 'package:jarvis_ui/theme/jarvis_theme.dart';
import 'package:jarvis_ui/widgets/global_search_dialog.dart';

import 'package:jarvis_ui/screens/admin_hub_screen.dart';
import 'package:jarvis_ui/screens/chat_screen.dart';
import 'package:jarvis_ui/screens/config_screen.dart';
import 'package:jarvis_ui/screens/dashboard_screen.dart';
import 'package:jarvis_ui/screens/identity_screen.dart';
import 'package:jarvis_ui/screens/skills_screen.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    ChatScreen(),
    DashboardScreen(),
    SkillsScreen(),
    AdminHubScreen(),
    IdentityScreen(),
  ];

  void _openSearch() {
    showDialog(
      context: context,
      builder: (_) => GlobalSearchDialog(
        onNavigate: (pageIndex) {
          Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => const ConfigScreen(),
            ),
          );
        },
      ),
    );
  }

  void _navigateTab(int index) {
    if (index >= 0 && index < _screens.length) {
      setState(() => _currentIndex = index);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final themeProvider = context.watch<ThemeProvider>();
    final isDark = themeProvider.isDark;

    return CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.keyK, control: true):
            _openSearch,
        const SingleActivator(LogicalKeyboardKey.digit1, control: true):
            () => _navigateTab(0),
        const SingleActivator(LogicalKeyboardKey.digit2, control: true):
            () => _navigateTab(1),
        const SingleActivator(LogicalKeyboardKey.digit3, control: true):
            () => _navigateTab(2),
        const SingleActivator(LogicalKeyboardKey.digit4, control: true):
            () => _navigateTab(3),
        const SingleActivator(LogicalKeyboardKey.digit5, control: true):
            () => _navigateTab(4),
      },
      child: Focus(
        autofocus: true,
        child: Scaffold(
          body: IndexedStack(
            index: _currentIndex,
            children: _screens,
          ),
          bottomNavigationBar: Container(
            decoration: BoxDecoration(
              color: Theme.of(context).cardColor,
              border: Border(
                top: BorderSide(
                  color: isDark
                      ? JarvisTheme.border
                      : const Color(0xFFE0E0E8),
                ),
              ),
            ),
            child: SafeArea(
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
                child: Row(
                  children: [
                    // Main navigation tabs
                    ..._buildNavItems(l),
                    // Spacer
                    const SizedBox(width: 4),
                    // Divider
                    Container(
                      width: 1,
                      height: 32,
                      color: isDark
                          ? JarvisTheme.border
                          : const Color(0xFFE0E0E8),
                    ),
                    const SizedBox(width: 4),
                    // Search button
                    _BottomBarAction(
                      icon: Icons.search,
                      label: 'Search',
                      color: JarvisTheme.accent,
                      onTap: _openSearch,
                    ),
                    // Theme toggle
                    _BottomBarAction(
                      icon: isDark ? Icons.light_mode : Icons.dark_mode,
                      label: isDark ? 'Light' : 'Dark',
                      color: JarvisTheme.orange,
                      onTap: () => themeProvider.toggle(),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _buildNavItems(AppLocalizations l) {
    final items = [
      (Icons.chat_bubble_outline, Icons.chat_bubble, l.chat, '^1'),
      (Icons.dashboard_outlined, Icons.dashboard, l.dashboard, '^2'),
      (Icons.extension_outlined, Icons.extension, l.skills, '^3'),
      (
        Icons.admin_panel_settings_outlined,
        Icons.admin_panel_settings,
        l.adminTitle,
        '^4',
      ),
      (Icons.psychology_outlined, Icons.psychology, l.identity, '^5'),
    ];

    return List.generate(items.length, (i) {
      final (iconOutlined, iconFilled, label, shortcut) = items[i];
      final selected = i == _currentIndex;
      return Expanded(
        child: InkWell(
          onTap: () => setState(() => _currentIndex = i),
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  selected ? iconFilled : iconOutlined,
                  size: 22,
                  color: selected
                      ? JarvisTheme.accent
                      : Theme.of(context).iconTheme.color,
                ),
                const SizedBox(height: 2),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight:
                        selected ? FontWeight.w600 : FontWeight.normal,
                    color: selected
                        ? JarvisTheme.accent
                        : Theme.of(context).textTheme.bodySmall?.color,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 1),
                Text(
                  shortcut,
                  style: TextStyle(
                    fontSize: 8,
                    color: JarvisTheme.textTertiary,
                    fontFamily: 'monospace',
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    });
  }
}

class _BottomBarAction extends StatelessWidget {
  const _BottomBarAction({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 20, color: color),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(fontSize: 9, color: color),
            ),
          ],
        ),
      ),
    );
  }
}
