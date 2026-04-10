import 'package:flutter_test/flutter_test.dart';
import 'package:cognithor_ui/main.dart';

void main() {
  testWidgets('App builds without error', (WidgetTester tester) async {
    await tester.pumpWidget(const JarvisApp());
    // Verify the app title appears on the splash screen.
    expect(find.text('Jarvis'), findsWidgets);
  });
}
