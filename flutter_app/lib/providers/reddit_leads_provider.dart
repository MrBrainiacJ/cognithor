import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:jarvis_ui/services/api_client.dart';

/// A single Reddit lead.
class RedditLead {
  RedditLead.fromJson(Map<String, dynamic> json)
      : id = json['id']?.toString() ?? '',
        postId = json['post_id']?.toString() ?? '',
        subreddit = json['subreddit']?.toString() ?? '',
        title = json['title']?.toString() ?? '',
        body = json['body']?.toString() ?? '',
        url = json['url']?.toString() ?? '',
        author = json['author']?.toString() ?? '',
        intentScore = (json['intent_score'] as num?)?.toInt() ?? 0,
        scoreReason = json['score_reason']?.toString() ?? '',
        replyDraft = json['reply_draft']?.toString() ?? '',
        replyFinal = json['reply_final']?.toString() ?? '',
        status = json['status']?.toString() ?? 'new',
        upvotes = (json['upvotes'] as num?)?.toInt() ?? 0,
        numComments = (json['num_comments'] as num?)?.toInt() ?? 0,
        detectedAt = (json['detected_at'] as num?)?.toDouble() ?? 0;

  final String id;
  final String postId;
  final String subreddit;
  final String title;
  final String body;
  final String url;
  final String author;
  final int intentScore;
  final String scoreReason;
  String replyDraft;
  String replyFinal;
  String status;
  final int upvotes;
  final int numComments;
  final double detectedAt;

  String get effectiveReply => replyFinal.isNotEmpty ? replyFinal : replyDraft;

  String get timeAgo {
    final diff = DateTime.now().difference(
        DateTime.fromMillisecondsSinceEpoch((detectedAt * 1000).toInt()));
    if (diff.inDays > 0) return '${diff.inDays}d ago';
    if (diff.inHours > 0) return '${diff.inHours}h ago';
    if (diff.inMinutes > 0) return '${diff.inMinutes}m ago';
    return 'just now';
  }
}

/// State management for the Reddit Leads tab.
class RedditLeadsProvider extends ChangeNotifier {
  ApiClient? _api;
  Timer? _pollTimer;

  List<RedditLead> _leads = [];
  Map<String, dynamic> _stats = {};
  bool _loading = false;
  bool _scanning = false;
  String? _error;
  String _statusFilter = '';
  int _minScoreFilter = 0;

  List<RedditLead> get leads => _leads;
  Map<String, dynamic> get stats => _stats;
  bool get loading => _loading;
  bool get scanning => _scanning;
  String? get error => _error;
  String get statusFilter => _statusFilter;
  int get minScoreFilter => _minScoreFilter;

  int get newCount => _leads.where((l) => l.status == 'new').length;
  int get reviewedCount => _leads.where((l) => l.status == 'reviewed').length;
  int get repliedCount => _leads.where((l) => l.status == 'replied').length;

  void init(ApiClient api) {
    _api = api;
    fetchLeads();
    fetchStats();
    _startPolling();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      fetchLeads();
      fetchStats();
    });
  }

  void setStatusFilter(String status) {
    _statusFilter = status;
    fetchLeads();
  }

  void setMinScoreFilter(int score) {
    _minScoreFilter = score;
    fetchLeads();
  }

  Future<void> fetchLeads() async {
    if (_api == null) return;
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      final resp = await _api!.getRedditLeads(
        status: _statusFilter.isEmpty ? null : _statusFilter,
        minScore: _minScoreFilter > 0 ? _minScoreFilter : null,
      );
      if (resp.containsKey('error')) {
        _error = resp['error'].toString();
      } else {
        final list = resp['leads'] as List<dynamic>? ?? [];
        _leads = list
            .map((j) => RedditLead.fromJson(j as Map<String, dynamic>))
            .toList();
      }
    } catch (e) {
      _error = e.toString();
    }
    _loading = false;
    notifyListeners();
  }

  Future<void> fetchStats() async {
    if (_api == null) return;
    try {
      final resp = await _api!.getRedditLeadStats();
      if (!resp.containsKey('error')) {
        _stats = resp['stats'] as Map<String, dynamic>? ?? {};
      }
    } catch (_) {}
    notifyListeners();
  }

  Future<bool> scanNow() async {
    if (_api == null) return false;
    _scanning = true;
    notifyListeners();
    try {
      final resp = await _api!.scanRedditLeads();
      _scanning = false;
      if (resp.containsKey('error')) {
        _error = resp['error'].toString();
        notifyListeners();
        return false;
      }
      await fetchLeads();
      await fetchStats();
      return true;
    } catch (e) {
      _scanning = false;
      _error = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> updateLead(String id, {String? status, String? replyFinal}) async {
    if (_api == null) return false;
    try {
      final body = <String, dynamic>{};
      if (status != null) body['status'] = status;
      if (replyFinal != null) body['reply_final'] = replyFinal;
      final resp = await _api!.updateRedditLead(id, body);
      if (!resp.containsKey('error')) {
        await fetchLeads();
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<bool> replyToLead(String id, {String mode = 'clipboard'}) async {
    if (_api == null) return false;
    try {
      final resp = await _api!.replyToRedditLead(id, mode: mode);
      if (resp['success'] == true) {
        await fetchLeads();
        return true;
      }
    } catch (_) {}
    return false;
  }
}
