# matplotlib stub

`matplotlib-99.0.0-py3-none-any.whl` is an **empty package** that satisfies
prophet's `matplotlib>=2.0.0` requirement so the real library (≈90 MB with its
dependencies) is not installed. Prophet only uses matplotlib for optional
plotting and guards the import, so forecasting is unaffected.

It is referenced from `requirements.txt`, which keeps the Vercel function bundle
under the 250 MB limit. Rebuild with:

```
pip wheel --no-deps -w vendor vendor/matplotlib-stub
```
