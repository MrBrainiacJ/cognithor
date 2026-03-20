import 'package:flutter/material.dart';
import 'package:jarvis_ui/l10n/generated/app_localizations.dart';
import 'package:jarvis_ui/theme/jarvis_theme.dart';
import 'package:jarvis_ui/widgets/jarvis_confirmation_dialog.dart';
import 'package:jarvis_ui/widgets/neon_card.dart';

/// Sidebar drawer showing past chat sessions grouped by folder.
class ChatHistoryDrawer extends StatelessWidget {
  const ChatHistoryDrawer({
    super.key,
    required this.sessions,
    required this.folders,
    required this.activeSessionId,
    required this.onSelectSession,
    required this.onNewChat,
    required this.onDeleteSession,
    required this.onRenameSession,
    required this.onMoveToFolder,
  });

  final List<Map<String, dynamic>> sessions;
  final List<String> folders;
  final String? activeSessionId;
  final ValueChanged<String> onSelectSession;
  final VoidCallback onNewChat;
  final ValueChanged<String> onDeleteSession;
  final void Function(String sessionId, String newTitle) onRenameSession;
  final void Function(String sessionId, String folder) onMoveToFolder;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);

    // Group sessions by folder
    final Map<String, List<Map<String, dynamic>>> grouped = {};
    for (final session in sessions) {
      final folder = session['folder']?.toString().trim() ?? '';
      grouped.putIfAbsent(folder, () => []).add(session);
    }

    // Sort: named folders first (alphabetically), then unfiled ('')
    final sortedFolders = grouped.keys.toList()
      ..sort((a, b) {
        if (a.isEmpty && b.isEmpty) return 0;
        if (a.isEmpty) return 1;
        if (b.isEmpty) return -1;
        return a.compareTo(b);
      });

    return Drawer(
      backgroundColor: theme.scaffoldBackgroundColor,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.horizontal(right: Radius.circular(16)),
      ),
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 8, 8),
              child: Row(
                children: [
                  const Icon(
                    Icons.history,
                    color: JarvisTheme.sectionChat,
                    size: JarvisTheme.iconSizeMd,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      l.chatHistory,
                      style: theme.textTheme.titleLarge?.copyWith(
                        color: JarvisTheme.sectionChat,
                      ),
                    ),
                  ),
                  FilledButton.icon(
                    onPressed: onNewChat,
                    icon: const Icon(Icons.add, size: 18),
                    label: Text(l.newChat),
                    style: FilledButton.styleFrom(
                      backgroundColor:
                          JarvisTheme.sectionChat.withValues(alpha: 0.15),
                      foregroundColor: JarvisTheme.sectionChat,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 8),
                      shape: RoundedRectangleBorder(
                        borderRadius:
                            BorderRadius.circular(JarvisTheme.buttonRadius),
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const Divider(height: 1),

            // Sessions list grouped by folder
            Expanded(
              child: sessions.isEmpty
                  ? Center(
                      child: Text(
                        l.noMessages,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.textTheme.bodySmall?.color,
                        ),
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      itemCount: sortedFolders.length,
                      itemBuilder: (context, folderIndex) {
                        final folderName = sortedFolders[folderIndex];
                        final folderSessions = grouped[folderName]!;
                        return _FolderSection(
                          folderName: folderName,
                          sessions: folderSessions,
                          activeSessionId: activeSessionId,
                          allFolders: folders,
                          onSelectSession: (id) {
                            onSelectSession(id);
                            Navigator.of(context).pop();
                          },
                          onDeleteSession: onDeleteSession,
                          onRenameSession: onRenameSession,
                          onMoveToFolder: onMoveToFolder,
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FolderSection extends StatefulWidget {
  const _FolderSection({
    required this.folderName,
    required this.sessions,
    required this.activeSessionId,
    required this.allFolders,
    required this.onSelectSession,
    required this.onDeleteSession,
    required this.onRenameSession,
    required this.onMoveToFolder,
  });

  final String folderName;
  final List<Map<String, dynamic>> sessions;
  final String? activeSessionId;
  final List<String> allFolders;
  final ValueChanged<String> onSelectSession;
  final ValueChanged<String> onDeleteSession;
  final void Function(String sessionId, String newTitle) onRenameSession;
  final void Function(String sessionId, String folder) onMoveToFolder;

  @override
  State<_FolderSection> createState() => _FolderSectionState();
}

class _FolderSectionState extends State<_FolderSection> {
  bool _expanded = true;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final displayName =
        widget.folderName.isEmpty ? l.noFolder : widget.folderName;
    final count = widget.sessions.length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Folder header
        NeonCard(
          tint: widget.folderName.isEmpty ? null : JarvisTheme.sectionChat,
          glowOnHover: true,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          onTap: () => setState(() => _expanded = !_expanded),
          child: Row(
            children: [
              Icon(
                widget.folderName.isEmpty
                    ? Icons.chat_bubble_outline
                    : (_expanded ? Icons.folder_open : Icons.folder),
                size: 18,
                color: widget.folderName.isEmpty
                    ? theme.iconTheme.color
                    : JarvisTheme.sectionChat,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  displayName,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: widget.folderName.isEmpty
                        ? null
                        : JarvisTheme.sectionChat,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                decoration: BoxDecoration(
                  color: JarvisTheme.sectionChat.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  l.sessionCount(count),
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontSize: 11,
                    color: JarvisTheme.sectionChat,
                  ),
                ),
              ),
              const SizedBox(width: 4),
              Icon(
                _expanded ? Icons.expand_less : Icons.expand_more,
                size: 18,
                color: theme.textTheme.bodySmall?.color,
              ),
            ],
          ),
        ),
        const SizedBox(height: 4),

        // Session cards
        if (_expanded)
          ...widget.sessions.map((session) {
            final sessionId = session['session_id']?.toString() ??
                session['id']?.toString() ??
                '';
            final isActive = sessionId == widget.activeSessionId;
            return Padding(
              padding: const EdgeInsets.only(left: 16, bottom: 6),
              child: _SessionCard(
                session: session,
                isActive: isActive,
                allFolders: widget.allFolders,
                onTap: () => widget.onSelectSession(sessionId),
                onDelete: () async {
                  final confirmed = await JarvisConfirmationDialog.show(
                    context,
                    title: l.deleteChat,
                    message: l.confirmDeleteChat,
                    confirmLabel: l.delete,
                    icon: Icons.delete_outline,
                  );
                  if (confirmed && context.mounted) {
                    widget.onDeleteSession(sessionId);
                  }
                },
                onRename: () => _showRenameDialog(context, sessionId, session),
                onMoveToFolder: (folder) =>
                    widget.onMoveToFolder(sessionId, folder),
              ),
            );
          }),

        const SizedBox(height: 8),
      ],
    );
  }

  void _showRenameDialog(
    BuildContext context,
    String sessionId,
    Map<String, dynamic> session,
  ) {
    final l = AppLocalizations.of(context);
    final currentTitle = session['title']?.toString().trim() ?? '';
    final controller = TextEditingController(text: currentTitle);

    showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: Theme.of(context).cardColor,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(JarvisTheme.cardRadius),
          side: BorderSide(color: Theme.of(context).dividerColor),
        ),
        icon: const Icon(Icons.edit, color: JarvisTheme.sectionChat,
            size: JarvisTheme.iconSizeLg),
        title: Text(l.editTitle),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: InputDecoration(
            hintText: l.untitledChat,
            border: const OutlineInputBorder(),
          ),
          onSubmitted: (value) => Navigator.of(ctx).pop(value.trim()),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(l.cancel),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(controller.text.trim()),
            style: ElevatedButton.styleFrom(
              backgroundColor: JarvisTheme.sectionChat,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(JarvisTheme.buttonRadius),
              ),
            ),
            child: Text(l.save),
          ),
        ],
      ),
    ).then((newTitle) {
      if (newTitle != null && newTitle.isNotEmpty && newTitle != currentTitle) {
        widget.onRenameSession(sessionId, newTitle);
      }
    });
  }
}

class _SessionCard extends StatelessWidget {
  const _SessionCard({
    required this.session,
    required this.isActive,
    required this.allFolders,
    required this.onTap,
    required this.onDelete,
    required this.onRename,
    required this.onMoveToFolder,
  });

  final Map<String, dynamic> session;
  final bool isActive;
  final List<String> allFolders;
  final VoidCallback onTap;
  final VoidCallback onDelete;
  final VoidCallback onRename;
  final ValueChanged<String> onMoveToFolder;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final title =
        session['title']?.toString().trim().isNotEmpty == true
            ? session['title'].toString()
            : l.untitledChat;
    final messageCount = session['message_count'] as int? ?? 0;
    final lastActivity = session['last_activity']?.toString();

    return NeonCard(
      tint: isActive ? JarvisTheme.sectionChat : null,
      glowOnHover: true,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      onTap: onTap,
      child: Row(
        children: [
          // Chat icon
          Icon(
            Icons.chat_bubble_outline,
            size: 18,
            color: isActive
                ? JarvisTheme.sectionChat
                : Theme.of(context).iconTheme.color,
          ),
          const SizedBox(width: 10),

          // Title + meta
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontWeight: isActive ? FontWeight.w600 : null,
                        color: isActive ? JarvisTheme.sectionChat : null,
                      ),
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    if (lastActivity != null) ...[
                      Text(
                        _formatRelativeTime(lastActivity, l),
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(width: 8),
                    ],
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(
                        color: JarvisTheme.sectionChat.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        l.messagesCount(messageCount.toString()),
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              fontSize: 11,
                              color: JarvisTheme.sectionChat,
                            ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // 3-dot menu
          PopupMenuButton<String>(
            icon: Icon(Icons.more_vert, size: 18,
                color: Theme.of(context).textTheme.bodySmall?.color),
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
            itemBuilder: (ctx) => [
              PopupMenuItem(
                value: 'rename',
                child: Row(
                  children: [
                    const Icon(Icons.edit, size: 18),
                    const SizedBox(width: 8),
                    Text(l.renameChat),
                  ],
                ),
              ),
              PopupMenuItem(
                value: 'move',
                child: Row(
                  children: [
                    const Icon(Icons.folder_outlined, size: 18),
                    const SizedBox(width: 8),
                    Text(l.moveToFolder),
                  ],
                ),
              ),
              const PopupMenuDivider(),
              PopupMenuItem(
                value: 'delete',
                child: Row(
                  children: [
                    Icon(Icons.delete_outline, size: 18,
                        color: JarvisTheme.red),
                    const SizedBox(width: 8),
                    Text(l.delete,
                        style: TextStyle(color: JarvisTheme.red)),
                  ],
                ),
              ),
            ],
            onSelected: (action) {
              switch (action) {
                case 'rename':
                  onRename();
                case 'move':
                  _showMoveToFolderDialog(context);
                case 'delete':
                  onDelete();
              }
            },
          ),
        ],
      ),
    );
  }

  void _showMoveToFolderDialog(BuildContext context) {
    showDialog<String>(
      context: context,
      builder: (ctx) => _MoveToFolderDialog(
        folders: allFolders,
        currentFolder: session['folder']?.toString().trim() ?? '',
      ),
    ).then((folder) {
      if (folder != null) {
        onMoveToFolder(folder);
      }
    });
  }

  String _formatRelativeTime(String isoTimestamp, AppLocalizations l) {
    try {
      final dt = DateTime.parse(isoTimestamp);
      final now = DateTime.now();
      final diff = now.difference(dt);

      if (diff.inSeconds < 60) return l.justNow;
      if (diff.inMinutes < 60) return l.minutesAgo(diff.inMinutes.toString());
      if (diff.inHours < 24) return l.hoursAgo(diff.inHours.toString());
      return l.daysAgo(diff.inDays.toString());
    } catch (_) {
      return '';
    }
  }
}

class _MoveToFolderDialog extends StatefulWidget {
  const _MoveToFolderDialog({
    required this.folders,
    required this.currentFolder,
  });

  final List<String> folders;
  final String currentFolder;

  @override
  State<_MoveToFolderDialog> createState() => _MoveToFolderDialogState();
}

class _MoveToFolderDialogState extends State<_MoveToFolderDialog> {
  bool _creatingNew = false;
  final _newFolderController = TextEditingController();

  @override
  void dispose() {
    _newFolderController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);

    return AlertDialog(
      backgroundColor: theme.cardColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(JarvisTheme.cardRadius),
        side: BorderSide(color: theme.dividerColor),
      ),
      icon: const Icon(Icons.folder_outlined, color: JarvisTheme.sectionChat,
          size: JarvisTheme.iconSizeLg),
      title: Text(l.moveToFolder),
      content: SizedBox(
        width: 280,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // "Unfiled" option to remove from folder
            if (widget.currentFolder.isNotEmpty)
              ListTile(
                leading: const Icon(Icons.remove_circle_outline, size: 20),
                title: Text(l.noFolder),
                dense: true,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                onTap: () => Navigator.of(context).pop(''),
              ),

            // Existing folders
            ...widget.folders
                .where((f) => f != widget.currentFolder)
                .map((folder) => ListTile(
                      leading: const Icon(Icons.folder, size: 20),
                      title: Text(folder),
                      dense: true,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                      onTap: () => Navigator.of(context).pop(folder),
                    )),

            const Divider(),

            // New folder creation
            if (_creatingNew)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: TextField(
                  controller: _newFolderController,
                  autofocus: true,
                  decoration: InputDecoration(
                    hintText: l.folderName,
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                      icon: const Icon(Icons.check),
                      onPressed: _submitNewFolder,
                    ),
                  ),
                  onSubmitted: (_) => _submitNewFolder(),
                ),
              )
            else
              ListTile(
                leading: const Icon(Icons.create_new_folder,
                    size: 20, color: JarvisTheme.sectionChat),
                title: Text(l.newFolder,
                    style: const TextStyle(color: JarvisTheme.sectionChat)),
                dense: true,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                onTap: () => setState(() => _creatingNew = true),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(l.cancel),
        ),
      ],
    );
  }

  void _submitNewFolder() {
    final name = _newFolderController.text.trim();
    if (name.isNotEmpty) {
      Navigator.of(context).pop(name);
    }
  }
}
