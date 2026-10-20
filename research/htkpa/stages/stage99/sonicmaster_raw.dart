// Stage99 diagnostic-only worker: compiled against a private COPY of clo_dsp.dart.
// It invokes the existing SonicMaster WaveNet path, not the CLO fitting pipeline.
import 'dart:js_interop';
import 'dart:typed_data';
import 'clo_dsp.dart';

@JS('self')
external _WorkerGlobal get _self;

extension type _WorkerGlobal(JSObject _) implements JSObject {
  external set onmessage(JSFunction callback);
  external void postMessage(JSObject data, JSArray<JSArrayBuffer> transfer);
}
extension type _MessageEvent(JSObject _) implements JSObject {
  external JSObject get data;
}
extension type _Request(JSObject _) implements JSObject {
  external String get type;
  external String get namJson;
  external JSFloat64Array get input;
}
extension type _Result._(JSObject _) implements JSObject {
  external factory _Result({String type, JSFloat64Array output});
}
extension type _Failure._(JSObject _) implements JSObject {
  external factory _Failure({String type, String error});
}
extension type _WithBuffer(JSObject _) implements JSObject {
  external JSArrayBuffer get buffer;
}

void main() {
  _self.onmessage = ((_MessageEvent event) {
    try {
      final req = _Request(event.data);
      if (req.type != 'raw') throw StateError('unsupported diagnostic request');
      final Float64List mono = req.input.toDart;
      if (mono.length != 8192) throw StateError('expected 8192 mono samples');
      final response = stage99RawInference(req.namJson, mono).toJS;
      _self.postMessage(_Result(type: 'raw', output: response),
        <JSArrayBuffer>[_WithBuffer(response).buffer].toJS);
    } catch (e) {
      _self.postMessage(_Failure(type: 'error', error: e.toString()),
        <JSArrayBuffer>[].toJS);
    }
  }).toJS;
}
