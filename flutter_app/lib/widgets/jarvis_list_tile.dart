import 'package:flutter/material.dart';
import 'package:cognithor_ui/theme/jarvis_theme.dart';

class JarvisListTile extends StatelessWidget {
  const JarvisListTile({
    super.key,
    required this.title,
    this.subtitle,
    this.leading,
    this.trailing,
    this.onTap,
    this.dense = false,
  });

  final String title;
  final String? subtitle;
  final Widget? leading;
  final Widget? trailing;
  final VoidCallback? onTap;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final verticalPad = dense ? JarvisTheme.spacingSm : 12.0;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(JarvisTheme.cardRadius),
      child: Padding(
        padding: EdgeInsets.symmetric(
          horizontal: JarvisTheme.spacing,
          vertical: verticalPad,
        ),
        child: Row(
          children: [
            if (leading != null) ...[
              leading!,
              const SizedBox(width: JarvisTheme.spacingSm),
            ],
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    title,
                    style: theme.textTheme.bodyLarge,
                  ),
                  if (subtitle != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(
                        subtitle!,
                        style: theme.textTheme.bodySmall,
                      ),
                    ),
                ],
              ),
            ),
            if (trailing != null) ...[
              const SizedBox(width: JarvisTheme.spacingSm),
              trailing!,
            ],
          ],
        ),
      ),
    );
  }
}
