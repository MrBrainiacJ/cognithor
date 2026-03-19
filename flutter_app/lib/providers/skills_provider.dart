/// Skills & marketplace state provider.
library;

import 'package:flutter/foundation.dart';
import 'package:jarvis_ui/services/api_client.dart';

class SkillsProvider extends ChangeNotifier {
  ApiClient? _api;

  void setApi(ApiClient? api) {
    _api = api;
  }

  List<dynamic> featured = [];
  List<dynamic> trending = [];
  List<dynamic> categories = [];
  List<dynamic> searchResults = [];
  List<dynamic> installed = [];
  String searchQuery = '';
  bool isLoading = false;
  String? error;

  Future<void> loadFeatured() async {
    if (_api == null) return;
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      final data = await _api!.getMarketplaceFeatured();
      featured = data['featured'] as List<dynamic>? ?? data['skills'] as List<dynamic>? ?? [];
    } catch (e) {
      error = e.toString();
    }
    isLoading = false;
    notifyListeners();
  }

  Future<void> loadTrending() async {
    if (_api == null) return;
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      final data = await _api!.getMarketplaceTrending();
      trending = data['trending'] as List<dynamic>? ?? data['skills'] as List<dynamic>? ?? [];
    } catch (e) {
      error = e.toString();
    }
    isLoading = false;
    notifyListeners();
  }

  Future<void> loadCategories() async {
    if (_api == null) return;
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      final data = await _api!.getMarketplaceCategories();
      categories = data['categories'] is List ? data['categories'] as List : [];
    } catch (e) {
      error = e.toString();
    }
    isLoading = false;
    notifyListeners();
  }

  Future<void> search(String q) async {
    if (_api == null) return;
    searchQuery = q;
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      final data = await _api!.searchMarketplace(q);
      searchResults = data['results'] as List<dynamic>? ?? [];
    } catch (e) {
      error = e.toString();
    }
    isLoading = false;
    notifyListeners();
  }

  Future<void> loadInstalled() async {
    if (_api == null) return;
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      final data = await _api!.getInstalledSkills();
      installed = data['installed'] as List<dynamic>? ?? data['skills'] as List<dynamic>? ?? [];
    } catch (e) {
      error = e.toString();
    }
    isLoading = false;
    notifyListeners();
  }

  Future<void> installSkill(String id) async {
    if (_api == null) return;
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      await _api!.installSkill(id);
      await loadInstalled();
    } catch (e) {
      error = e.toString();
      isLoading = false;
      notifyListeners();
    }
  }

  Future<void> uninstallSkill(String id) async {
    if (_api == null) return;
    isLoading = true;
    error = null;
    notifyListeners();
    try {
      await _api!.uninstallSkill(id);
      await loadInstalled();
    } catch (e) {
      error = e.toString();
      isLoading = false;
      notifyListeners();
    }
  }
}
