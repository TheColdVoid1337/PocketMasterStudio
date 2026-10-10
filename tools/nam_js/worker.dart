// PocketMasterStudio standalone dart2js Web Worker, derived from SonicMaster (MIT).
// No Flutter/package:web runtime dependency. Compile once at build time.
// Protocol:
//  {type:"probe",namJson,di:Float32Array,level} -> {type:"probe",level,response:Float64Array}
//  {type:"finish",namJson,di:Float32Array,responses:[{level,response}]}
//     -> {type:"finish",arrayA:Float32Array,arrayB:Float32Array,gains:Float32Array}
//  failure -> {type:"error",error,level}
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
extension type _ProbeData(JSObject _) implements JSObject {
  external double get level;
  external JSFloat64Array get response;
}
extension type _Request(JSObject _) implements JSObject {
  external String get type;
  external String get namJson;
  external JSFloat32Array get di;
  external double get level;
  external JSArray<_ProbeData> get responses;
}
extension type _ProbeResult._(JSObject _) implements JSObject {
  external factory _ProbeResult({
    String type, double level, JSFloat64Array response,
  });
}
extension type _FitResult._(JSObject _) implements JSObject {
  external factory _FitResult({
    String type, JSFloat32Array arrayA, JSFloat32Array arrayB,
    JSFloat32Array gains,
  });
}
extension type _ErrorResult._(JSObject _) implements JSObject {
  external factory _ErrorResult({
    String type, String error, double level,
  });
}
extension type _WithBuffer(JSObject _) implements JSObject {
  external JSArrayBuffer get buffer;
}
void main() {
  _self.onmessage = (( _MessageEvent event) {
    final request = _Request(event.data);
    double level = 0.0;
    try {
      if (request.type == 'probe') {
        level = request.level;
        final response = runOneProbeLevel(
          request.namJson, request.di.toDart, level,
        ).toJS;
        final transfer = <JSArrayBuffer>[_WithBuffer(response).buffer].toJS;
        _self.postMessage(
          _ProbeResult(type: 'probe', level: level, response: response), transfer,
        );
      } else if (request.type == 'finish') {
        final responses = request.responses.toDart
            .map((item) => (item.level, item.response.toDart))
            .toList();
        final arrays = finishFromProbeResponses(
          request.namJson, request.di.toDart, responses,
        );
        final a = arrays.arrayA.toJS;
        final b = arrays.arrayB.toJS;
        final gains = Float32List.fromList(arrays.gains).toJS;
        _self.postMessage(
          _FitResult(type: 'finish', arrayA: a, arrayB: b, gains: gains),
          <JSArrayBuffer>[
            _WithBuffer(a).buffer, _WithBuffer(b).buffer,
            _WithBuffer(gains).buffer,
          ].toJS,
        );
      } else {
        throw StateError('Unsupported DSP worker request');
      }
    } catch (e) {
      _self.postMessage(
        _ErrorResult(type: 'error', error: e.toString(), level: level),
        <JSArrayBuffer>[].toJS,
      );
    }
  }).toJS;
}
