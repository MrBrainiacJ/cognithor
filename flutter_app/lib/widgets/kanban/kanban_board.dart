import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:jarvis_ui/providers/kanban_provider.dart';
import 'package:jarvis_ui/widgets/kanban/kanban_column.dart';

class KanbanBoard extends StatelessWidget {
  const KanbanBoard({super.key});

  static const _columnOrder = ['todo', 'in_progress', 'verifying', 'done', 'blocked'];

  static const _columnLabels = {
    'todo': 'To Do',
    'in_progress': 'In Progress',
    'verifying': 'Verifying',
    'done': 'Done',
    'blocked': 'Blocked',
  };

  static const _columnColors = {
    'todo': Colors.grey,
    'in_progress': Colors.blueAccent,
    'verifying': Colors.orange,
    'done': Colors.green,
    'blocked': Colors.red,
  };

  @override
  Widget build(BuildContext context) {
    return Consumer<KanbanProvider>(
      builder: (context, kanban, _) {
        if (kanban.loading && kanban.tasks.isEmpty) {
          return const Center(child: CircularProgressIndicator());
        }

        final grouped = kanban.tasksByStatus;

        return SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: _columnOrder.map((status) {
              return Padding(
                padding: const EdgeInsets.only(right: 12),
                child: KanbanColumn(
                  status: status,
                  label: _columnLabels[status] ?? status,
                  color: _columnColors[status] ?? Colors.grey,
                  tasks: grouped[status] ?? [],
                ),
              );
            }).toList(),
          ),
        );
      },
    );
  }
}
