import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:visionpath_app/main.dart';

void main() {
  testWidgets('VisionPathApp initial widget smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: VisionPathApp(),
      ),
    );

    expect(find.byType(VisionPathApp), findsOneWidget);

    // Fast-forward past entrance animation delays so pending timers resolve
    await tester.pump(const Duration(milliseconds: 500));
  });
}
