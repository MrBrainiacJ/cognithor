import 'package:flutter/material.dart';

class KanbanConfigDialog extends StatefulWidget {
  const KanbanConfigDialog({super.key, this.availableAgents = const []});

  final List<String> availableAgents;

  @override
  State<KanbanConfigDialog> createState() => _KanbanConfigDialogState();
}

class _KanbanConfigDialogState extends State<KanbanConfigDialog> {
  bool _autoChat = true;
  bool _autoCron = true;
  bool _autoEvolution = true;
  bool _autoAgents = true;
  int _maxAutoTasks = 10;
  int _maxSubtaskDepth = 3;
  int _archiveDays = 30;
  String _defaultPriority = 'medium';
  String _defaultAgent = 'jarvis';

  static const _priorities = ['low', 'medium', 'high', 'urgent'];
  List<String> get _agents => widget.availableAgents.isNotEmpty
      ? widget.availableAgents
      : ['jarvis'];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Dialog(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 500, maxHeight: 600),
        child: Scaffold(
          appBar: AppBar(
            title: const Text('Kanban Settings'),
            leading: IconButton(
              icon: const Icon(Icons.close),
              onPressed: () => Navigator.pop(context),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, _buildConfig()),
                child: const Text('Save'),
              ),
            ],
          ),
          body: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Task Sources
              Text('Task Sources', style: theme.textTheme.titleMedium),
              const SizedBox(height: 8),
              SwitchListTile(
                title: const Text('From Chat'),
                subtitle: const Text('Auto-detect task creation in conversations'),
                value: _autoChat,
                onChanged: (v) => setState(() => _autoChat = v),
              ),
              SwitchListTile(
                title: const Text('From Cron Jobs'),
                subtitle: const Text('Create tasks from scheduled job results'),
                value: _autoCron,
                onChanged: (v) => setState(() => _autoCron = v),
              ),
              SwitchListTile(
                title: const Text('From Evolution Engine'),
                subtitle: const Text('Tasks for detected improvement opportunities'),
                value: _autoEvolution,
                onChanged: (v) => setState(() => _autoEvolution = v),
              ),
              SwitchListTile(
                title: const Text('From Agents'),
                subtitle: const Text('Allow agents to create tasks during execution'),
                value: _autoAgents,
                onChanged: (v) => setState(() => _autoAgents = v),
              ),

              const Divider(height: 32),

              // Guards
              Text('Guards', style: theme.textTheme.titleMedium),
              const SizedBox(height: 8),
              ListTile(
                title: const Text('Max auto-tasks per session'),
                trailing: SizedBox(
                  width: 60,
                  child: DropdownButton<int>(
                    value: _maxAutoTasks,
                    isExpanded: true,
                    items: [5, 10, 20, 50].map((v) =>
                      DropdownMenuItem(value: v, child: Text('$v')),
                    ).toList(),
                    onChanged: (v) => setState(() => _maxAutoTasks = v ?? 10),
                  ),
                ),
              ),
              ListTile(
                title: const Text('Max subtask depth'),
                trailing: SizedBox(
                  width: 60,
                  child: DropdownButton<int>(
                    value: _maxSubtaskDepth,
                    isExpanded: true,
                    items: [1, 2, 3, 4, 5].map((v) =>
                      DropdownMenuItem(value: v, child: Text('$v')),
                    ).toList(),
                    onChanged: (v) => setState(() => _maxSubtaskDepth = v ?? 3),
                  ),
                ),
              ),

              const Divider(height: 32),

              // Defaults
              Text('Defaults', style: theme.textTheme.titleMedium),
              const SizedBox(height: 8),
              ListTile(
                title: const Text('Default priority'),
                trailing: DropdownButton<String>(
                  value: _defaultPriority,
                  items: _priorities.map((p) =>
                    DropdownMenuItem(value: p, child: Text(p)),
                  ).toList(),
                  onChanged: (v) => setState(() => _defaultPriority = v ?? 'medium'),
                ),
              ),
              ListTile(
                title: const Text('Default agent'),
                trailing: DropdownButton<String>(
                  value: _defaultAgent,
                  items: _agents.map((a) =>
                    DropdownMenuItem(value: a, child: Text(a)),
                  ).toList(),
                  onChanged: (v) => setState(() => _defaultAgent = v ?? 'jarvis'),
                ),
              ),
              ListTile(
                title: const Text('Auto-archive after (days)'),
                trailing: SizedBox(
                  width: 60,
                  child: DropdownButton<int>(
                    value: _archiveDays,
                    isExpanded: true,
                    items: [7, 14, 30, 60, 90, 365].map((v) =>
                      DropdownMenuItem(value: v, child: Text('$v')),
                    ).toList(),
                    onChanged: (v) => setState(() => _archiveDays = v ?? 30),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Map<String, dynamic> _buildConfig() {
    return {
      'auto_create_from_chat': _autoChat,
      'auto_create_from_cron': _autoCron,
      'auto_create_from_evolution': _autoEvolution,
      'auto_create_from_agents': _autoAgents,
      'max_auto_tasks_per_session': _maxAutoTasks,
      'max_subtask_depth': _maxSubtaskDepth,
      'default_priority': _defaultPriority,
      'default_agent': _defaultAgent,
      'archive_after_days': _archiveDays,
    };
  }
}
