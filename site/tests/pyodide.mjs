// Runs Plain's own tests inside Pyodide (the Python the playground uses), under Node.
// This shows the browser runs the same Plain as your terminal.
//   node site/tests/pyodide.mjs        (after python site/build.py)
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const version = "314.0.7";
const { loadPyodide } = await import(path.join(root, "site/dist/pyodide", version, "pyodide.mjs"));

const pyodide = await loadPyodide({ indexURL: path.join(root, "site/dist/pyodide", version) + "/" });
pyodide.FS.mkdirTree("/plain");
pyodide.FS.mount(pyodide.FS.filesystems.NODEFS, { root }, "/plain");

const ok = pyodide.runPython(`
import io, sys, unittest
sys.path[:0] = ["/plain/src", "/plain"]
names = ["tests.test_golden", "tests.test_problems", "tests.test_docs", "tests.test_phrasings",
         "tests.test_catalog", "tests.test_parser", "tests.test_repl"]
suite = unittest.TestSuite(unittest.TestLoader().loadTestsFromName(n) for n in names)
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
print(f"Python {sys.version.split()[0]} in Pyodide")
print(stream.getvalue()[-4000:])
result.wasSuccessful()
`);
process.exit(ok ? 0 : 1);
