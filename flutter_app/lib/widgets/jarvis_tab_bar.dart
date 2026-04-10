import 'package:flutter/material.dart';
import 'package:cognithor_ui/theme/jarvis_theme.dart';

class JarvisTabBar extends StatelessWidget {
  const JarvisTabBar({
    super.key,
    required this.tabs,
    required this.selectedIndex,
    required this.onChanged,
    this.icons,
  });

  final List<String> tabs;
  final int selectedIndex;
  final ValueChanged<int> onChanged;
  final List<IconData>? icons;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: List.generate(tabs.length, (i) {
          final isSelected = i == selectedIndex;
          return GestureDetector(
            onTap: () => onChanged(i),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                border: Border(
                  bottom: BorderSide(
                    color: isSelected ? JarvisTheme.accent : Colors.transparent,
                    width: 2,
                  ),
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (icons != null && i < icons!.length) ...[
                    Icon(
                      icons![i],
                      size: JarvisTheme.iconSizeSm,
                      color: isSelected ? JarvisTheme.accent : JarvisTheme.textSecondary,
                    ),
                    const SizedBox(width: 6),
                  ],
                  Text(
                    tabs[i],
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: isSelected ? JarvisTheme.accent : JarvisTheme.textSecondary,
                      fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                    ),
                  ),
                ],
              ),
            ),
          );
        }),
      ),
    );
  }
}
