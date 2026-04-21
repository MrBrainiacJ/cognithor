import 'package:flutter/material.dart';
import 'package:cognithor_ui/theme/jarvis_theme.dart';

class JarvisEmptyState extends StatefulWidget {
  const JarvisEmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    this.action,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? action;

  @override
  State<JarvisEmptyState> createState() => _JarvisEmptyStateState();
}

class _JarvisEmptyStateState extends State<JarvisEmptyState>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulseController;
  late final Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.85, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(JarvisTheme.spacingXl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Gradient circle behind the pulsing icon
            ScaleTransition(
              scale: _pulseAnimation,
              child: Container(
                width: 96,
                height: 96,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      JarvisTheme.accent.withAlpha(30),
                      JarvisTheme.accent.withAlpha(5),
                    ],
                  ),
                ),
                child: Icon(
                  widget.icon,
                  size: 48,
                  color: JarvisTheme.accent.withAlpha(180),
                ),
              ),
            ),
            const SizedBox(height: JarvisTheme.spacingLg),
            Text(
              widget.title,
              style: theme.textTheme.titleLarge?.copyWith(
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
              textAlign: TextAlign.center,
            ),
            if (widget.subtitle != null) ...[
              const SizedBox(height: JarvisTheme.spacingSm),
              Text(
                widget.subtitle!,
                style: theme.textTheme.bodySmall?.copyWith(
                  fontSize: 13,
                  height: 1.5,
                ),
                textAlign: TextAlign.center,
              ),
            ],
            if (widget.action != null) ...[
              const SizedBox(height: JarvisTheme.spacingLg),
              widget.action!,
            ],
          ],
        ),
      ),
    );
  }
}
