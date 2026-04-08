import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:jarvis_ui/l10n/generated/app_localizations.dart';
import 'package:jarvis_ui/providers/admin_provider.dart';
import 'package:jarvis_ui/providers/connection_provider.dart';
import 'package:jarvis_ui/providers/kanban_provider.dart';
import 'package:jarvis_ui/providers/chat_provider.dart';
import 'package:jarvis_ui/widgets/kanban/kanban_board.dart';
import 'package:jarvis_ui/widgets/kanban/kanban_config_dialog.dart';
import 'package:jarvis_ui/widgets/kanban/task_dialog.dart';
import 'package:jarvis_ui/widgets/kanban/task_detail_sheet.dart';
import 'package:jarvis_ui/widgets/observe/kanban_panel.dart';

class KanbanScreen extends StatefulWidget {
  const KanbanScreen({super.key});

  @override
  State<KanbanScreen> createState() => _KanbanScreenState();
}

class _KanbanScreenState extends State<KanbanScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final conn = context.read<ConnectionProvider>();
      final kanban = context.read<KanbanProvider>();
      if (conn.state == JarvisConnectionState.connected) {
        kanban.setApiClient(conn.api);
      }
      kanban.fetchTasks();
      // Load agents for the agent picker dropdowns
      final admin = context.read<AdminProvider>();
      admin.setApi(conn.api);
      admin.loadAgents();
    });
  }

  List<String> get _agentNames {
    final admin = context.read<AdminProvider>();
    return admin.agents
        .map((a) => (a as Map<String, dynamic>)['name']?.toString() ?? '')
        .where((n) => n.isNotEmpty)
        .toList();
  }

  Future<void> _createTask() async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => TaskDialog(availableAgents: _agentNames),
    );
    if (result != null && mounted) {
      await context.read<KanbanProvider>().createTask(
            title: result['title'] as String,
            description: result['description'] as String? ?? '',
            priority: result['priority'] as String? ?? 'medium',
            assignedAgent: result['assigned_agent'] as String? ?? '',
            labels: (result['labels'] as List<String>?) ?? [],
          );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l = AppLocalizations.of(context)!;

    return Consumer<KanbanProvider>(
      builder: (context, kanban, _) {
        return Scaffold(
          body: Column(
            children: [
              // Toolbar
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                decoration: BoxDecoration(
                  border: Border(
                    bottom: BorderSide(
                      color: theme.dividerColor.withValues(alpha: 0.3),
                    ),
                  ),
                ),
                child: Row(
                  children: [
                    // Toggle
                    SegmentedButton<bool>(
                      segments: [
                        ButtonSegment(value: false, label: Text(l.kanbanMyTasks)),
                        ButtonSegment(value: true, label: Text(l.kanbanLivePipeline)),
                      ],
                      selected: {kanban.pipelineMode},
                      onSelectionChanged: (s) => kanban.togglePipelineMode(),
                      style: ButtonStyle(
                        visualDensity: VisualDensity.compact,
                        textStyle: WidgetStateProperty.all(
                          const TextStyle(fontSize: 12),
                        ),
                      ),
                    ),
                    const Spacer(),
                    if (!kanban.pipelineMode) ...[
                      // Stats badge
                      if (kanban.tasks.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(right: 12),
                          child: Text(
                            '${kanban.tasks.length} tasks',
                            style: TextStyle(
                              fontSize: 12,
                              color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                            ),
                          ),
                        ),
                      // New task button
                      FilledButton.icon(
                        onPressed: _createTask,
                        icon: const Icon(Icons.add, size: 18),
                        label: Text(l.kanbanNewTask),
                        style: FilledButton.styleFrom(
                          visualDensity: VisualDensity.compact,
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        icon: const Icon(Icons.settings_outlined),
                        onPressed: () {
                          showDialog(
                            context: context,
                            builder: (_) => KanbanConfigDialog(availableAgents: _agentNames),
                          );
                        },
                      ),
                    ],
                  ],
                ),
              ),
              // Board
              Expanded(
                child: kanban.pipelineMode
                    ? Consumer<ChatProvider>(
                        builder: (context, chat, _) {
                          return KanbanPanel(
                            entries: chat.pipeline
                                .map((p) => {
                                      'phase': p.phase,
                                      'status': p.status,
                                      'elapsed_ms': p.elapsedMs,
                                    })
                                .toList(),
                          );
                        },
                      )
                    : const KanbanBoard(),
              ),
            ],
          ),
        );
      },
    );
  }
}
