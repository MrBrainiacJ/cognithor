import 'package:cognithor_ui/l10n/generated/app_localizations.dart';
import 'package:cognithor_ui/providers/chat_provider.dart';
import 'package:cognithor_ui/providers/llm_backend_provider.dart';
import 'package:cognithor_ui/providers/voice_provider.dart';
import 'package:cognithor_ui/widgets/chat_input.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

LlmBackendProvider _mkBackendProvider(String active) {
  final p = LlmBackendProvider(apiBaseUrl: 'http://test');
  p.active = active;
  return p;
}

ChatProvider _mkChatProvider() {
  return ChatProvider();
}

Widget _wrap(Widget child, LlmBackendProvider bp, ChatProvider cp) {
  return MaterialApp(
    localizationsDelegates: const [
      AppLocalizations.delegate,
      GlobalMaterialLocalizations.delegate,
      GlobalWidgetsLocalizations.delegate,
    ],
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: MultiProvider(
        providers: [
          ChangeNotifierProvider<LlmBackendProvider>.value(value: bp),
          ChangeNotifierProvider<ChatProvider>.value(value: cp),
          ChangeNotifierProvider<VoiceProvider>(create: (_) => VoiceProvider()),
        ],
        child: child,
      ),
    ),
  );
}

void main() {
  testWidgets('paperclip opens popup menu with 4 entries', (tester) async {
    final bp = _mkBackendProvider('vllm');
    final cp = _mkChatProvider();
    await tester.pumpWidget(_wrap(
      ChatInput(onSend: (_) {}, onCancel: () {}),
      bp,
      cp,
    ));

    await tester.tap(find.byKey(const ValueKey('chat-input-paperclip')));
    await tester.pumpAndSettle();

    expect(find.text('Bild hochladen'), findsOneWidget);
    expect(find.text('Video hochladen'), findsOneWidget);
    expect(find.text('Datei hochladen'), findsOneWidget);
    expect(find.text('URL einfügen'), findsOneWidget);
  });

  testWidgets('Video entry disabled when active backend != vllm', (tester) async {
    final bp = _mkBackendProvider('ollama');
    final cp = _mkChatProvider();
    await tester.pumpWidget(_wrap(
      ChatInput(onSend: (_) {}, onCancel: () {}),
      bp,
      cp,
    ));

    await tester.tap(find.byKey(const ValueKey('chat-input-paperclip')));
    await tester.pumpAndSettle();

    final videoItem = tester.widget<PopupMenuItem<String>>(
      find.ancestor(
        of: find.text('Video hochladen'),
        matching: find.byType(PopupMenuItem<String>),
      ),
    );
    expect(videoItem.enabled, isFalse);
  });

  testWidgets('URL dialog accepts valid video URL and sets pending attachment',
      (tester) async {
    final bp = _mkBackendProvider('vllm');
    final cp = _mkChatProvider();
    await tester.pumpWidget(_wrap(
      ChatInput(onSend: (_) {}, onCancel: () {}),
      bp,
      cp,
    ));

    await tester.tap(find.byKey(const ValueKey('chat-input-paperclip')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('URL einfügen'));
    await tester.pumpAndSettle();

    // Dialog should be open (title + menu entry both contain "URL einfügen")
    expect(find.text('URL einfügen'), findsAtLeastNWidgets(1));
    // Scope the TextField lookup to the dialog — the ChatInput's own
    // TextField is also in the tree.
    final dialogField = find.descendant(
      of: find.byType(AlertDialog),
      matching: find.byType(TextField),
    );
    expect(dialogField, findsOneWidget);

    await tester.enterText(dialogField, 'https://x.com/clip.mp4');
    await tester.tap(find.text('Hinzufügen'));
    await tester.pumpAndSettle();

    expect(cp.pendingVideoAttachment, isNotNull);
    expect(cp.pendingVideoAttachment!['url'], 'https://x.com/clip.mp4');
  });

  testWidgets('URL dialog rejects non-video URL with snackbar', (tester) async {
    final bp = _mkBackendProvider('vllm');
    final cp = _mkChatProvider();
    await tester.pumpWidget(_wrap(
      ChatInput(onSend: (_) {}, onCancel: () {}),
      bp,
      cp,
    ));

    await tester.tap(find.byKey(const ValueKey('chat-input-paperclip')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('URL einfügen'));
    await tester.pumpAndSettle();

    final dialogField = find.descendant(
      of: find.byType(AlertDialog),
      matching: find.byType(TextField),
    );
    await tester.enterText(dialogField, 'https://example.com/page.html');
    await tester.tap(find.text('Hinzufügen'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Ungültige URL'), findsOneWidget);
    expect(cp.pendingVideoAttachment, isNull);
  });
}
