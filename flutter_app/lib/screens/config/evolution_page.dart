import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:jarvis_ui/providers/config_provider.dart';
import 'package:jarvis_ui/providers/connection_provider.dart';
import 'package:jarvis_ui/l10n/generated/app_localizations.dart';
import 'package:jarvis_ui/theme/jarvis_theme.dart';

class EvolutionPage extends StatefulWidget {
  const EvolutionPage({super.key});

  @override
  State<EvolutionPage> createState() => _EvolutionPageState();
}

class _EvolutionPageState extends State<EvolutionPage> {
  Map<String, dynamic>? _data;
  List<String> _goals = [];
  List<dynamic> _plans = [];
  bool _loading = true;
  bool _resuming = false;
  bool _creatingPlan = false;
  String? _error;
  String? _resumeResult;
  Timer? _refreshTimer;
  final _goalController = TextEditingController();
  final _planGoalController = TextEditingController();

  static const _steps = ['scout', 'research', 'build', 'reflect'];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _goalController.dispose();
    _planGoalController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final api = context.read<ConnectionProvider>().api;
      final results = await Future.wait([
        api.get('evolution/stats'),
        api.get('evolution/goals'),
        api.get('evolution/plans'),
      ]);
      if (!mounted) return;
      final goalsData = (results[1]['goals'] as List<dynamic>?) ?? [];
      setState(() {
        _data = results[0];
        _goals = goalsData.map((g) => g.toString()).toList();
        _plans = (results[2]['plans'] as List<dynamic>?) ?? [];
        _loading = false;
      });
      _refreshTimer?.cancel();
      _refreshTimer = Timer.periodic(
        const Duration(seconds: 15),
        (_) => _refresh(),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() { _loading = false; _error = e.toString(); });
    }
  }

  Future<void> _refresh() async {
    try {
      final api = context.read<ConnectionProvider>().api;
      final data = await api.get('evolution/stats');
      if (!mounted) return;
      setState(() { _data = data; });
    } catch (_) {}
  }

  Future<void> _resume() async {
    setState(() { _resuming = true; _resumeResult = null; });
    try {
      final api = context.read<ConnectionProvider>().api;
      await api.post('evolution/resume', {});
      if (!mounted) return;
      setState(() { _resuming = false; _resumeResult = 'Resume triggered'; });
      _refresh();
    } catch (e) {
      if (!mounted) return;
      setState(() { _resuming = false; _resumeResult = 'Error: $e'; });
    }
  }

  Color _usageColor(double pct) {
    if (pct > 80) return JarvisTheme.red;
    if (pct > 60) return JarvisTheme.orange;
    return JarvisTheme.green;
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);

    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null && _data == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 48, color: JarvisTheme.red),
            const SizedBox(height: 16),
            Text(_error!, style: TextStyle(color: JarvisTheme.textSecondary)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _load,
              icon: const Icon(Icons.refresh, size: 16),
              label: Text(l.retry),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildConfigCard(),
          const SizedBox(height: 16),
          _buildGoalsCard(),
          const SizedBox(height: 16),
          _buildPlansCard(),
          const SizedBox(height: 16),
          _buildStatusHeader(),
          const SizedBox(height: 16),
          _buildStepIndicator(),
          const SizedBox(height: 16),
          _buildResumeCard(),
          const SizedBox(height: 16),
          _buildResourceStatus(),
          const SizedBox(height: 16),
          _buildRecentActivity(),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  // -- Config Card (Enable/Disable + Settings) --------------------------------

  Widget _buildConfigCard() {
    return Consumer<ConfigProvider>(
      builder: (context, cfg, _) {
        final evo =
            (cfg.cfg['evolution'] as Map<String, dynamic>?) ?? <String, dynamic>{};
        final enabled = evo['enabled'] == true;
        final idleMinutes = (evo['idle_minutes'] as num?)?.toInt() ?? 5;
        final maxCycles = (evo['max_cycles_per_day'] as num?)?.toInt() ?? 10;

        return Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.settings, size: 20, color: JarvisTheme.accent),
                    const SizedBox(width: 8),
                    const Text(
                      'Configuration',
                      style:
                          TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                SwitchListTile(
                  title: const Text('Evolution Engine'),
                  subtitle: Text(
                    enabled
                        ? 'Active — learns autonomously during idle time'
                        : 'Disabled — enable to start autonomous learning',
                    style: TextStyle(
                      fontSize: 12,
                      color: JarvisTheme.textSecondary,
                    ),
                  ),
                  value: enabled,
                  activeThumbColor: JarvisTheme.green,
                  contentPadding: EdgeInsets.zero,
                  onChanged: (v) => cfg.set('evolution.enabled', v),
                ),
                const Divider(height: 24),
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Idle threshold',
                            style: TextStyle(
                                fontSize: 12,
                                color: JarvisTheme.textSecondary),
                          ),
                          const SizedBox(height: 4),
                          DropdownButton<int>(
                            value: idleMinutes,
                            isExpanded: true,
                            isDense: true,
                            items: [1, 2, 3, 5, 10, 15, 30, 60]
                                .map((m) => DropdownMenuItem(
                                      value: m,
                                      child: Text('$m min'),
                                    ))
                                .toList(),
                            onChanged: enabled
                                ? (v) {
                                    if (v != null) {
                                      cfg.set('evolution.idle_minutes', v);
                                    }
                                  }
                                : null,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 24),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Max cycles/day',
                            style: TextStyle(
                                fontSize: 12,
                                color: JarvisTheme.textSecondary),
                          ),
                          const SizedBox(height: 4),
                          DropdownButton<int>(
                            value: maxCycles,
                            isExpanded: true,
                            isDense: true,
                            items: [1, 3, 5, 10, 20, 50, 100]
                                .map((m) => DropdownMenuItem(
                                      value: m,
                                      child: Text('$m'),
                                    ))
                                .toList(),
                            onChanged: enabled
                                ? (v) {
                                    if (v != null) {
                                      cfg.set(
                                          'evolution.max_cycles_per_day', v);
                                    }
                                  }
                                : null,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  // -- Learning Goals Card ---------------------------------------------------

  Future<void> _saveGoals() async {
    try {
      final api = context.read<ConnectionProvider>().api;
      await api.put('evolution/goals', {'goals': _goals});
    } catch (_) {}
  }

  void _addGoal() {
    final text = _goalController.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _goals.add(text);
      _goalController.clear();
    });
    _saveGoals();
  }

  void _removeGoal(int index) {
    setState(() { _goals.removeAt(index); });
    _saveGoals();
  }

  Widget _buildGoalsCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.school, size: 20, color: JarvisTheme.accent),
                const SizedBox(width: 8),
                const Text(
                  'Learning Goals',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
                const Spacer(),
                Text(
                  '${_goals.length} topics',
                  style: TextStyle(
                      fontSize: 12, color: JarvisTheme.textSecondary),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Define what Cognithor should learn during idle time. '
              'The Evolution Engine will research these topics autonomously.',
              style: TextStyle(
                  fontSize: 12, color: JarvisTheme.textSecondary),
            ),
            const SizedBox(height: 16),
            // Input row
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _goalController,
                    decoration: InputDecoration(
                      hintText: 'e.g. Python async patterns',
                      hintStyle: TextStyle(
                          fontSize: 13, color: JarvisTheme.textTertiary),
                      isDense: true,
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 10),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                    style: const TextStyle(fontSize: 13),
                    onSubmitted: (_) => _addGoal(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: Icon(Icons.add_circle, color: JarvisTheme.green),
                  onPressed: _addGoal,
                  tooltip: 'Add goal',
                ),
              ],
            ),
            if (_goals.isNotEmpty) ...[
              const SizedBox(height: 12),
              ..._goals.asMap().entries.map((e) {
                final idx = e.key;
                final goal = e.value;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    children: [
                      Icon(Icons.circle, size: 6,
                          color: JarvisTheme.accent),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(goal,
                            style: const TextStyle(fontSize: 13)),
                      ),
                      IconButton(
                        icon: Icon(Icons.close, size: 16,
                            color: JarvisTheme.red),
                        onPressed: () => _removeGoal(idx),
                        visualDensity: VisualDensity.compact,
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(
                            minWidth: 24, minHeight: 24),
                      ),
                    ],
                  ),
                );
              }),
            ] else ...[
              const SizedBox(height: 16),
              Center(
                child: Text(
                  'No learning goals defined yet.\n'
                  'Add topics above to start autonomous evolution.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 12,
                    color: JarvisTheme.textTertiary,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  // -- Learning Plans Card --------------------------------------------------

  Widget _buildPlansCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.school, size: 20, color: JarvisTheme.accent),
              const SizedBox(width: 8),
              const Text('Learning Plans',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              const Spacer(),
              Text('${_plans.length} plans',
                  style: TextStyle(
                      fontSize: 12, color: JarvisTheme.textSecondary)),
            ]),
            const SizedBox(height: 12),
            _buildCreatePlanRow(),
            if (_plans.isEmpty) ...[
              const SizedBox(height: 16),
              Center(
                child: Text(
                  'No deep learning plans yet.\n'
                  'Complex goals are automatically promoted to plans.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 12,
                    color: JarvisTheme.textTertiary,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ),
            ],
            ..._plans
                .map((p) => _buildPlanTile(p as Map<String, dynamic>)),
          ],
        ),
      ),
    );
  }

  Widget _buildCreatePlanRow() {
    return Row(children: [
      Expanded(
        child: TextField(
          controller: _planGoalController,
          decoration: InputDecoration(
            hintText: 'e.g. Become an expert in German insurance law',
            hintStyle:
                TextStyle(fontSize: 12, color: JarvisTheme.textTertiary),
            isDense: true,
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            border:
                OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
          ),
          style: const TextStyle(fontSize: 13),
          onSubmitted: (_) => _createPlan(),
        ),
      ),
      const SizedBox(width: 8),
      _creatingPlan
          ? const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(strokeWidth: 2))
          : IconButton(
              icon: Icon(Icons.rocket_launch, color: JarvisTheme.accent),
              onPressed: _createPlan,
              tooltip: 'Create Learning Plan',
            ),
    ]);
  }

  Future<void> _createPlan() async {
    final goal = _planGoalController.text.trim();
    if (goal.isEmpty) return;
    setState(() {
      _creatingPlan = true;
    });
    try {
      final api = context.read<ConnectionProvider>().api;
      await api.post('evolution/plans', {'goal': goal});
      _planGoalController.clear();
      await _load();
    } catch (_) {}
    if (!mounted) return;
    setState(() {
      _creatingPlan = false;
    });
  }

  Widget _buildPlanTile(Map<String, dynamic> plan) {
    final goal = (plan['goal'] as String?) ?? '';
    final status = (plan['status'] as String?) ?? 'planning';
    final sgTotal = (plan['sub_goals_total'] as int?) ?? 0;
    final sgDone = (plan['sub_goals_done'] as int?) ?? 0;
    final coverage = ((plan['coverage_score'] as num?) ?? 0.0).toDouble();
    final quality = ((plan['quality_score'] as num?) ?? 0.0).toDouble();
    final chunks = (plan['total_chunks_indexed'] as int?) ?? 0;
    final entities = (plan['total_entities_created'] as int?) ?? 0;
    final planId = (plan['id'] as String?) ?? '';

    final statusColor = switch (status) {
      'active' => JarvisTheme.green,
      'paused' => JarvisTheme.orange,
      'completed' => JarvisTheme.accent,
      'error' => JarvisTheme.red,
      _ => JarvisTheme.textSecondary,
    };

    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: statusColor.withValues(alpha: 0.3)),
          color: statusColor.withValues(alpha: 0.05),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Title + status + actions
            Row(children: [
              Expanded(
                child: Text(goal,
                    style: const TextStyle(
                        fontSize: 14, fontWeight: FontWeight.w600),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis),
              ),
              const SizedBox(width: 8),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(status.toUpperCase(),
                    style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        color: statusColor)),
              ),
              if (status == 'active')
                IconButton(
                  icon:
                      Icon(Icons.pause, size: 18, color: JarvisTheme.orange),
                  onPressed: () => _updatePlan(planId, 'pause'),
                  visualDensity: VisualDensity.compact,
                  padding: EdgeInsets.zero,
                  constraints:
                      const BoxConstraints(minWidth: 30, minHeight: 30),
                ),
              if (status == 'paused')
                IconButton(
                  icon: Icon(Icons.play_arrow,
                      size: 18, color: JarvisTheme.green),
                  onPressed: () => _updatePlan(planId, 'resume'),
                  visualDensity: VisualDensity.compact,
                  padding: EdgeInsets.zero,
                  constraints:
                      const BoxConstraints(minWidth: 30, minHeight: 30),
                ),
              IconButton(
                icon: Icon(Icons.delete_outline,
                    size: 18, color: JarvisTheme.red),
                onPressed: () => _updatePlan(planId, 'delete'),
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                constraints:
                    const BoxConstraints(minWidth: 30, minHeight: 30),
              ),
            ]),
            const SizedBox(height: 8),
            // Progress bar
            Row(children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: sgTotal > 0 ? sgDone / sgTotal : 0,
                    backgroundColor:
                        JarvisTheme.textTertiary.withValues(alpha: 0.2),
                    valueColor:
                        AlwaysStoppedAnimation<Color>(statusColor),
                    minHeight: 6,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text('$sgDone/$sgTotal',
                  style: TextStyle(
                      fontSize: 11, color: JarvisTheme.textSecondary)),
            ]),
            const SizedBox(height: 6),
            // Stats row
            Row(children: [
              _planStat(
                  Icons.analytics, '${(coverage * 100).toInt()}%', 'Coverage'),
              _planStat(
                  Icons.quiz, '${(quality * 100).toInt()}%', 'Quality'),
              _planStat(Icons.description, '$chunks', 'Chunks'),
              _planStat(Icons.hub, '$entities', 'Entities'),
            ]),
          ],
        ),
      ),
    );
  }

  Widget _planStat(IconData icon, String value, String label) {
    return Expanded(
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 12, color: JarvisTheme.textTertiary),
        const SizedBox(width: 3),
        Text(value,
            style:
                const TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
        const SizedBox(width: 2),
        Text(label,
            style:
                TextStyle(fontSize: 10, color: JarvisTheme.textTertiary)),
      ]),
    );
  }

  Future<void> _updatePlan(String planId, String action) async {
    try {
      final api = context.read<ConnectionProvider>().api;
      await api.patch('evolution/plans/$planId', {'action': action});
      await _load();
    } catch (_) {}
  }

  // -- Status Header Card ---------------------------------------------------

  Color _modeColor(String mode) {
    return switch (mode) {
      'offline' => JarvisTheme.green,
      'hybrid' => JarvisTheme.orange,
      'online' => JarvisTheme.accent,
      _ => JarvisTheme.textSecondary,
    };
  }

  IconData _modeIcon(String mode) {
    return switch (mode) {
      'offline' => Icons.wifi_off,
      'hybrid' => Icons.swap_horiz,
      'online' => Icons.cloud,
      _ => Icons.help_outline,
    };
  }

  String _modeDescription(String mode) {
    return switch (mode) {
      'offline' => 'Memory search only — no LLM costs',
      'hybrid' => 'Memory + Web search — moderate costs',
      'online' => 'Full research + LLM synthesis — budget applies',
      _ => '',
    };
  }

  Widget _buildStatusHeader() {
    final running = _data?['running'] as bool? ?? false;
    final isIdle = _data?['is_idle'] as bool? ?? true;
    final idleSec = (_data?['idle_seconds'] as num?)?.toInt() ?? 0;
    final totalCycles = _data?['total_cycles'] as int? ?? 0;
    final cyclesToday = _data?['cycles_today'] as int? ?? 0;
    final skillsCreated = _data?['total_skills_created'] as int? ?? 0;
    final mode = (_data?['operation_mode'] as String?) ?? 'offline';

    final Color statusColor;
    final String statusLabel;
    if (!running) {
      statusColor = JarvisTheme.red;
      statusLabel = 'Stopped';
    } else if (isIdle) {
      statusColor = JarvisTheme.orange;
      statusLabel = 'Idle';
    } else {
      statusColor = JarvisTheme.green;
      statusLabel = 'Running';
    }

    final mColor = _modeColor(mode);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.auto_awesome, size: 20, color: JarvisTheme.accent),
                const SizedBox(width: 8),
                const Text(
                  'Evolution Engine',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
                const Spacer(),
                // Mode badge
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: mColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                    border:
                        Border.all(color: mColor.withValues(alpha: 0.4)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(_modeIcon(mode), size: 14, color: mColor),
                      const SizedBox(width: 4),
                      Text(
                        mode.toUpperCase(),
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: mColor,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                // Status badge
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                        color: statusColor.withValues(alpha: 0.4)),
                  ),
                  child: Text(
                    statusLabel,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: statusColor,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              _modeDescription(mode),
              style: TextStyle(fontSize: 12, color: JarvisTheme.textSecondary),
            ),
            if (isIdle && running && idleSec > 0) ...[
              const SizedBox(height: 4),
              Text(
                'Idle for ${_formatDuration(idleSec)}',
                style: TextStyle(
                    fontSize: 12, color: JarvisTheme.textSecondary),
              ),
            ],
            const SizedBox(height: 16),
            Row(
              children: [
                _statChip('Total Cycles', '$totalCycles'),
                _statChip('Today', '$cyclesToday'),
                _statChip('Skills Created', '$skillsCreated'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _statChip(String label, String value) {
    return Expanded(
      child: Column(
        children: [
          Text(value,
              style: const TextStyle(
                  fontSize: 20, fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text(label,
              style: TextStyle(
                  fontSize: 11, color: JarvisTheme.textSecondary),
              textAlign: TextAlign.center),
        ],
      ),
    );
  }

  // -- Step Indicator -------------------------------------------------------

  Widget _buildStepIndicator() {
    final checkpoint =
        _data?['checkpoint'] as Map<String, dynamic>? ?? {};
    final stepsCompleted = (checkpoint['steps_completed'] as List<dynamic>?)
            ?.map((e) => e.toString().toLowerCase())
            .toSet() ??
        {};
    final currentStep =
        (checkpoint['step_name'] as String?)?.toLowerCase() ?? '';
    final topic = checkpoint['research_topic'] as String? ?? '';
    final cycleId = checkpoint['cycle_id'] as int? ?? 0;

    if (cycleId == 0 && stepsCompleted.isEmpty) {
      return const SizedBox.shrink();
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.linear_scale, size: 20, color: JarvisTheme.accent),
                const SizedBox(width: 8),
                Text('Cycle #$cycleId',
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: List.generate(_steps.length * 2 - 1, (i) {
                if (i.isOdd) {
                  // Connector line
                  final prevStep = _steps[i ~/ 2];
                  final completed = stepsCompleted.contains(prevStep);
                  return Expanded(
                    child: Container(
                      height: 2,
                      color: completed
                          ? JarvisTheme.green
                          : JarvisTheme.textSecondary.withValues(alpha: 0.3),
                    ),
                  );
                }
                final stepIdx = i ~/ 2;
                final step = _steps[stepIdx];
                final completed = stepsCompleted.contains(step);
                final isCurrent = step == currentStep;

                Color color;
                IconData icon;
                if (completed && !isCurrent) {
                  color = JarvisTheme.green;
                  icon = Icons.check_circle;
                } else if (isCurrent) {
                  color = JarvisTheme.accent;
                  icon = Icons.radio_button_checked;
                } else {
                  color = JarvisTheme.textSecondary.withValues(alpha: 0.4);
                  icon = Icons.radio_button_unchecked;
                }

                return Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(icon, size: 22, color: color),
                    const SizedBox(height: 4),
                    Text(
                      step[0].toUpperCase() + step.substring(1),
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight:
                            isCurrent ? FontWeight.w700 : FontWeight.w500,
                        color: color,
                      ),
                    ),
                  ],
                );
              }),
            ),
            if (topic.isNotEmpty) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Icon(Icons.topic, size: 16, color: JarvisTheme.textSecondary),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(topic,
                        style: TextStyle(
                            fontSize: 12,
                            color: JarvisTheme.textSecondary),
                        overflow: TextOverflow.ellipsis),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  // -- Resume Card ----------------------------------------------------------

  Widget _buildResumeCard() {
    final resume =
        _data?['resume'] as Map<String, dynamic>? ?? {};
    final hasCheckpoint = resume['has_checkpoint'] as bool? ?? false;
    final isComplete = resume['is_complete'] as bool? ?? true;

    if (!hasCheckpoint || isComplete) return const SizedBox.shrink();

    final cycleId = resume['cycle_id'] as int? ?? 0;
    final lastStep = (resume['last_step'] as String?) ?? '?';
    final nextStep = (resume['next_step'] as String?) ?? '?';
    final topic = (resume['research_topic'] as String?) ?? '';

    return Card(
      color: JarvisTheme.orange.withValues(alpha: 0.08),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.pause_circle_filled,
                    size: 20, color: JarvisTheme.orange),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Cycle #$cycleId interrupted at: '
                    '${lastStep[0].toUpperCase()}${lastStep.substring(1)}',
                    style: const TextStyle(
                        fontSize: 14, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
            if (topic.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text('Topic: $topic',
                  style: TextStyle(
                      fontSize: 12, color: JarvisTheme.textSecondary)),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                Text('Next step: ${nextStep[0].toUpperCase()}${nextStep.substring(1)}',
                    style: TextStyle(
                        fontSize: 12, color: JarvisTheme.textSecondary)),
                const Spacer(),
                ElevatedButton.icon(
                  onPressed: _resuming ? null : _resume,
                  icon: _resuming
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.play_arrow, size: 16),
                  label: Text(_resuming ? 'Resuming...' : 'Resume'),
                ),
              ],
            ),
            if (_resumeResult != null) ...[
              const SizedBox(height: 8),
              Text(_resumeResult!,
                  style: TextStyle(
                    fontSize: 12,
                    color: _resumeResult!.startsWith('Error')
                        ? JarvisTheme.red
                        : JarvisTheme.green,
                  )),
            ],
          ],
        ),
      ),
    );
  }

  // -- Resource Status ------------------------------------------------------

  Widget _buildResourceStatus() {
    final res =
        _data?['resources'] as Map<String, dynamic>? ?? {};
    final available = res['available'] as bool? ?? false;
    final paused = res['paused'] as bool? ?? false;
    final cpu = (res['cpu_percent'] as num?)?.toDouble() ?? 0;
    final ram = (res['ram_percent'] as num?)?.toDouble() ?? 0;
    final gpu = (res['gpu_util_percent'] as num?)?.toDouble();

    final statusMsg =
        paused ? 'System busy -- evolution paused' : 'Resources available';
    final statusColor = paused ? JarvisTheme.orange : JarvisTheme.green;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.monitor_heart,
                    size: 20, color: JarvisTheme.accent),
                const SizedBox(width: 8),
                const Text('Resources',
                    style:
                        TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                const Spacer(),
                Icon(
                  available && !paused
                      ? Icons.check_circle
                      : Icons.warning,
                  size: 16,
                  color: statusColor,
                ),
                const SizedBox(width: 6),
                Text(statusMsg,
                    style: TextStyle(fontSize: 11, color: statusColor)),
              ],
            ),
            const SizedBox(height: 16),
            _resourceBar('CPU', cpu, '${cpu.toStringAsFixed(1)}%',
                Icons.developer_board),
            const SizedBox(height: 10),
            _resourceBar(
                'RAM', ram, '${ram.toStringAsFixed(1)}%', Icons.memory),
            if (gpu != null) ...[
              const SizedBox(height: 10),
              _resourceBar('GPU', gpu, '${gpu.toStringAsFixed(1)}%',
                  Icons.videogame_asset),
            ],
          ],
        ),
      ),
    );
  }

  Widget _resourceBar(
      String label, double percent, String detail, IconData icon) {
    final clamped = percent.clamp(0.0, 100.0);
    final color = _usageColor(clamped);

    return Row(
      children: [
        Icon(icon, size: 18, color: JarvisTheme.textSecondary),
        const SizedBox(width: 8),
        SizedBox(
          width: 36,
          child: Text(label,
              style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: JarvisTheme.textSecondary)),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: clamped / 100,
              minHeight: 10,
              backgroundColor: color.withValues(alpha: 0.15),
              valueColor: AlwaysStoppedAnimation(color),
            ),
          ),
        ),
        const SizedBox(width: 12),
        SizedBox(
          width: 60,
          child: Text(detail,
              textAlign: TextAlign.right,
              style: TextStyle(
                  fontSize: 12,
                  color: color,
                  fontWeight: FontWeight.w500,
                  fontFamily: 'monospace')),
        ),
      ],
    );
  }

  // -- Recent Activity ------------------------------------------------------

  Widget _buildRecentActivity() {
    final recent =
        (_data?['recent_results'] as List<dynamic>?) ?? [];
    if (recent.isEmpty) return const SizedBox.shrink();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.history, size: 20, color: JarvisTheme.accent),
                const SizedBox(width: 8),
                const Text('Recent Activity',
                    style:
                        TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 12),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: DataTable(
                columnSpacing: 20,
                headingTextStyle: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 12,
                  color: JarvisTheme.textSecondary,
                ),
                dataTextStyle: const TextStyle(fontSize: 12),
                columns: const [
                  DataColumn(label: Text('#'), numeric: true),
                  DataColumn(label: Text('Topic')),
                  DataColumn(label: Text('Skill')),
                  DataColumn(label: Text('Duration')),
                  DataColumn(label: Text('Status')),
                ],
                rows: recent.take(5).map((r) {
                  final e = r is Map<String, dynamic>
                      ? r
                      : <String, dynamic>{};
                  final cycle = e['cycle'] as int? ?? 0;
                  final topic = (e['topic'] as String?) ?? '';
                  final skill = (e['skill'] as String?) ?? '';
                  final durationMs =
                      (e['duration_ms'] as num?)?.toInt() ?? 0;
                  final skipped = e['skipped'] as bool? ?? false;
                  final reason = (e['reason'] as String?) ?? '';

                  final duration = durationMs >= 1000
                      ? '${(durationMs / 1000).toStringAsFixed(1)}s'
                      : '${durationMs}ms';

                  return DataRow(cells: [
                    DataCell(Text('$cycle')),
                    DataCell(ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 180),
                      child: Text(topic,
                          overflow: TextOverflow.ellipsis),
                    )),
                    DataCell(Text(skill.isNotEmpty ? skill : '--')),
                    DataCell(Text(duration,
                        style: const TextStyle(fontFamily: 'monospace'))),
                    DataCell(
                      skipped
                          ? Tooltip(
                              message: reason,
                              child: Text('Skipped',
                                  style: TextStyle(
                                      color: JarvisTheme.orange,
                                      fontWeight: FontWeight.w500)))
                          : Text('OK',
                              style: TextStyle(
                                  color: JarvisTheme.green,
                                  fontWeight: FontWeight.w500)),
                    ),
                  ]);
                }).toList(),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // -- Helpers --------------------------------------------------------------

  String _formatDuration(int seconds) {
    if (seconds < 60) return '${seconds}s';
    if (seconds < 3600) return '${seconds ~/ 60}m ${seconds % 60}s';
    final h = seconds ~/ 3600;
    final m = (seconds % 3600) ~/ 60;
    return '${h}h ${m}m';
  }
}
