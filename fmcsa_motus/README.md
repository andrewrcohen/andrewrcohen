# FMCSA Motus API Exercise

CLI that exercises the public FMCSA Motus APIs already running in production:

- Motus REST at [motus.dot.gov](https://motus.dot.gov/public/search)
- Motus SODA datasets on [data.transportation.gov](https://www.fmcsa.dot.gov/registration/fmcsa-data-dissemination-program)
- Optional [QCMobile](https://mobile.fmcsa.dot.gov/QCDevsite/docs/qcApi) lookup API

Requires Python 3.9+ and no third-party packages.

```bash
python3 -m fmcsa_motus.exercise --usdot 44110 --name GREYHOUND
python3 -m fmcsa_motus.exercise --suite motus --usdot 44110
python3 -m fmcsa_motus.exercise --suite soda --usdot 44110
FMCSA_WEBKEY=your-webkey python3 -m fmcsa_motus.exercise --suite qcmobile --usdot 44110
python3 -m unittest fmcsa_motus.tests.test_exercise
```

Tax identifiers (`ein`, `ssn`, and similar) are redacted in `--raw` output.
