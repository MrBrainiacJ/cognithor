import 'dart:async';

import 'package:flutter/material.dart';
import 'package:jarvis_ui/theme/jarvis_theme.dart';

class JarvisSearchBar extends StatefulWidget {
  const JarvisSearchBar({
    super.key,
    this.hintText = 'Search…',
    this.onChanged,
    this.onClear,
    this.controller,
  });

  final String hintText;
  final ValueChanged<String>? onChanged;
  final VoidCallback? onClear;
  final TextEditingController? controller;

  @override
  State<JarvisSearchBar> createState() => _JarvisSearchBarState();
}

class _JarvisSearchBarState extends State<JarvisSearchBar> {
  late final TextEditingController _controller;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _controller = widget.controller ?? TextEditingController();
    _controller.addListener(_onTextChanged);
  }

  void _onTextChanged() {
    setState(() {});
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      widget.onChanged?.call(_controller.text);
    });
  }

  void _clear() {
    _controller.clear();
    widget.onClear?.call();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    if (widget.controller == null) {
      _controller.dispose();
    } else {
      _controller.removeListener(_onTextChanged);
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textColor = theme.textTheme.bodyMedium?.color;
    final borderColor = theme.dividerColor;

    return TextField(
      controller: _controller,
      style: TextStyle(color: textColor),
      decoration: InputDecoration(
        hintText: widget.hintText,
        filled: true,
        fillColor: theme.cardColor,
        prefixIcon: Icon(
          Icons.search,
          color: JarvisTheme.textSecondary,
          size: JarvisTheme.iconSizeMd,
        ),
        suffixIcon: _controller.text.isNotEmpty
            ? IconButton(
                icon: Icon(
                  Icons.clear,
                  color: JarvisTheme.textSecondary,
                  size: JarvisTheme.iconSizeSm,
                ),
                onPressed: _clear,
              )
            : null,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(JarvisTheme.cardRadius),
          borderSide: BorderSide(color: borderColor),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(JarvisTheme.cardRadius),
          borderSide: BorderSide(color: borderColor),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(JarvisTheme.cardRadius),
          borderSide: BorderSide(color: JarvisTheme.accent),
        ),
      ),
    );
  }
}
