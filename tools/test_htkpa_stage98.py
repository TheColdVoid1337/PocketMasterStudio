"""Stage98 source-first NAM integration contracts; synthetic DSP != real NAM."""
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'research/htkpa/open_nam/GO.py'
SPEC = importlib.util.spec_from_file_location('htkpa_open_nam_stage98', SCRIPT)
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)


class Stage98Tests(unittest.TestCase):
    def test_pin_and_no_network_side_effect(self):
        self.assertEqual(M.PIN, '0b3d3c97b0859a3a8c92a8628c4dd89a25eb5842')
        self.assertEqual(M.sha(SCRIPT), __import__('hashlib').sha256(SCRIPT.read_bytes()).hexdigest())

    def test_missing_checkout_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'no auto-fetch'):
                M.verify_source(Path(d))

    def test_fake_complete_checkout_revision_and_gitlink_gate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for rel in ('.git/HEAD','LICENSE','NAM/get_dsp.h', 'NAM/get_dsp.cpp',
                        'NAM/dsp.h','NAM/container.cpp','NAM/slimmable.h',
                        'Dependencies/nlohmann/json.hpp','Dependencies/eigen/Eigen/Dense'):
                p = root / rel
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text('MIT License' if rel=='LICENSE' else 'stub')
            revs = [M.PIN,'','bc3b39870ecb690a623a3f49149a358b95c5781d']
            with mock.patch.object(M, 'cmd', side_effect=revs) as c:
                x = M.verify_source(root)
            self.assertEqual(x['source_commit'], M.PIN)
            self.assertEqual(c.call_count, 3)
            with mock.patch.object(M,'cmd', side_effect=['0'*40]):
                with self.assertRaisesRegex(ValueError, 'pinned'):
                    M.verify_source(root)
            with mock.patch.object(M,'cmd', side_effect=[M.PIN, '', '1'*40]):
                with self.assertRaisesRegex(ValueError, 'Eigen'):
                    M.verify_source(root)

    def test_build_preflight_does_not_touch_upstream_on_wrong_revision(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                M.build(Path(d), Path(d) / 'output')
            self.assertFalse((Path(d) / 'output').exists())

    def test_run_rejects_missing_manifest_and_binary(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'x.nam').write_text('{}')
            (root/'in.f64le').write_bytes(struct.pack('<d',0))
            with self.assertRaisesRegex(ValueError, 'manifest'):
                M.run(root,root/'x.nam',root/'in.f64le',root/'out.f64le',44100,64,'on',None)

    def test_reject_nonfinite_slim(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            dummy=root/'x.nam';dummy.write_text('{}')
            raw=root/'in.f64le';raw.write_bytes(struct.pack('<d',0))
            marker={'source_commit':M.PIN,'bridge_sha256':M.sha(M.HERE/'htkpa_nam_probe.cpp'),
                    'cmake_sha256':M.sha(M.HERE/'CMakeLists.txt'),
                    'binary_name':'dummy','binary_sha256':''}
            (root/M.MARKER).write_text(json.dumps(marker))
            (root/'dummy').write_text('fake executable')
            marker['binary_sha256']=M.sha(root/'dummy')
            (root/M.MARKER).write_text(json.dumps(marker))
            with self.assertRaisesRegex(ValueError,'slim'):
                M.run(root,dummy,raw,root/'out.f64le',44100,64,'on',math.nan)
            with self.assertRaisesRegex(ValueError,'rate'):
                M.run(root,dummy,raw,root/'out.f64le',2000,64,'on',None)

    def test_mock_native_binary_provenance_and_no_overwrite(self):
        # A fake executable validates *Python orchestration only*, not NAM DSP.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            mod=root/'fake.nam';mod.write_text('{}')
            raw=root/'input.f64le';raw.write_bytes(struct.pack('<dd', .25,-.125))
            binary=root/'mockprobe'
            binary.write_text('#!/usr/bin/env python3\nimport json,sys,shutil\na=sys.argv\nshutil.copyfile(a[a.index("--input-f64le")+1],a[a.index("--output-f64le")+1])\nprint(json.dumps({"status":"NAM_CORE_UPSTREAM_INFERENCE_COMPLETED","frames":2,"sample_rate":44100}))\n')
            binary.chmod(0o755)
            manifest={'source_commit':M.PIN,'bridge_sha256':M.sha(M.HERE/'htkpa_nam_probe.cpp'),
                      'cmake_sha256':M.sha(M.HERE/'CMakeLists.txt'),
                      'binary_name':'mockprobe','binary_sha256':M.sha(binary)}
            (root/M.MARKER).write_text(json.dumps(manifest))
            dest=root/'out.f64le'
            r=M.run(root,mod,raw,dest,44100,64,'on',None)
            self.assertEqual(r['frames'], 2)
            self.assertFalse(r['clo_generated'])
            self.assertTrue(dest.with_suffix('.f64le.provenance.json').is_file())
            self.assertEqual(dest.read_bytes(),raw.read_bytes())
            with self.assertRaisesRegex(ValueError,'overwrite'):
                M.run(root,mod,raw,dest,44100,64,'on',None)

    def test_smoke_requires_real_sample_rate(self):
        with tempfile.TemporaryDirectory() as d:
            model=Path(d)/'test.nam'
            model.write_text(json.dumps({'architecture':'WaveNet'}))
            with self.assertRaisesRegex(ValueError,'sample_rate unknown'):
                M.smoke(Path(d),model,None,64,'on',None)
            model.write_text(json.dumps({'sample_rate': 48000}))
            with self.assertRaisesRegex(ValueError,'differs'):
                M.smoke(Path(d),model,44100,64,'on',None)

    def test_smoke_deterministic_8192_frames_without_real_dsp_claim(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            model=root/'test.nam';model.write_text(json.dumps({'sample_rate':44100}))
            with mock.patch.object(M,'ROOT',root),mock.patch.object(M,'run',
              return_value={'status':'NAM_CORE_UPSTREAM_INFERENCE_COMPLETED','frames':8192}) as r:
                val=M.smoke(root,model,None,64,'on',None)
                self.assertEqual(val['stimulus_frames'],8192)
                self.assertEqual(val['comparison_to_vendor'],'NOT_PERFORMED')
                args=r.call_args.args
                self.assertEqual(args[4],44100)
                self.assertEqual(args[2].stat().st_size,8192*8)
                first_hash=val['stimulus_sha256']
                second=M.smoke(root,model,None,64,'on',None)
                self.assertEqual(first_hash,second['stimulus_sha256'])

    @unittest.skipUnless(shutil.which('c++'), 'native C++ compiler unavailable')
    def test_compiled_cpp_bridge_against_synthetic_fake_nam_api(self):
        # Compiles and runs our REAL bridge, but with deliberately fake NAM API.
        # This is NOT evidence that upstream NAM sources compiled or have numerical parity.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            hdr=root/'NAM';hdr.mkdir()
            (hdr/'dsp.h').write_text(textwrap.dedent('''
                #pragma once
                #include <cstddef>
                #define NAM_SAMPLE double
                namespace nam {
                class DSP { public:
                  virtual ~DSP() = default;
                  int NumInputChannels() const { return 1; }
                  int NumOutputChannels() const { return 1; }
                  double GetExpectedSampleRate() const { return 44100.; }
                  void SetPrewarmOnReset(bool) {}
                  void Reset(double, int) {}
                  virtual void process(double** x,double** y,int n) {
                    for(int i=0;i<n;++i)y[0][i]=2*x[0][i];
                  }
                }; }
            '''))
            (hdr/'get_dsp.h').write_text(textwrap.dedent('''
                #pragma once
                #include "dsp.h"
                #include <filesystem>
                #include <memory>
                #include <optional>
                namespace nam {
                struct DspLoadOptions { std::optional<bool> prewarm; };
                inline std::unique_ptr<DSP> get_dsp(const std::filesystem::path&, DspLoadOptions) {
                  return std::make_unique<DSP>();
                } }
            '''))
            (hdr/'slimmable.h').write_text(textwrap.dedent('''
                #pragma once
                namespace nam {
                class SlimmableModel {
                  public: virtual ~SlimmableModel()=default;
                  virtual void SetSlimmableSize(double)=0;
                }; }
            '''))
            bin=root/'runner'
            s=M.HERE/'htkpa_nam_probe.cpp'
            result=subprocess.run(['c++','-std=c++20','-O0','-I'+str(root),str(s),'-o',str(bin)],
                                  capture_output=True,text=True)
            self.assertEqual(result.returncode, 0, result.stderr[:1500])
            inp=root/'in.f64le';inp.write_bytes(struct.pack('<ddd', 1.0,.5,-.25))
            out=root/'out.f64le'
            base=[str(bin),'--model',str(root/'fake.nam'),'--input-f64le',str(inp),
                  '--output-f64le',str(out),'--sample-rate','44100','--block','2']
            success=subprocess.run(base,capture_output=True,text=True)
            self.assertEqual(success.returncode,0,success.stderr[:700])
            self.assertEqual(struct.unpack('<ddd',out.read_bytes()),(2.,1.,-.5))
            self.assertEqual(json.loads(success.stdout)['frames'],3)
            wrong_args = [str(bin),'--model',str(root/'fake.nam'),'--input-f64le',str(inp),
                          '--output-f64le',str(root/'wrong_rate.f64le'),
                          '--sample-rate','48000','--block','2']
            wrong=subprocess.run(wrong_args,capture_output=True,text=True)
            self.assertNotEqual(wrong.returncode,0)
            self.assertIn('rate',wrong.stderr.lower())


if __name__=='__main__':
    unittest.main()
