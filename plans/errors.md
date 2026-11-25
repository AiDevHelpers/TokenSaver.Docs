# Workflow to Reduce AI‑Generated Coding Errors by ~70%

A practical, repeatable workflow that dramatically cuts down syntax issues, hallucinated APIs, structural mistakes, and logic bugs in AI‑generated code.

---

## 1. Generate Code Inside a Strict Sandbox

Tell the AI to output **only code**, inside a single file, with no prose outside the block.  
This prevents structural hallucinations and missing braces.

---

## 2. Auto‑Format Immediately

Run the output through a formatter before reviewing it.

- Prettier (JS/TS)  
- Black (Python)  
- Rustfmt (Rust)  
- Gofmt (Go)

Formatting fixes indentation, brace alignment, semicolons, and spacing.

---

## 3. Auto‑Lint the Code

Linting catches structural and logical issues early.

- ESLint  
- Ruff / Pylint  
- Clippy  
- Go vet

This removes undefined variables, wrong imports, unreachable code, and async mistakes.

---

## 4. Run a Typechecker

Typechecking eliminates the biggest chunk of AI errors.

- TypeScript (`tsc`)  
- Pyright / MyPy  
- Rustc  
- Go vet

Catches wrong parameter types, wrong return types, missing fields, and incorrect generics.

---

## 5. Run Synthetic Tests

Generate tiny tests that validate the “shape” of the code:

- Function exists  
- Parameters match  
- Return type matches  
- Async behavior is correct  

These catch missing exports, wrong names, wrong argument order, and missing returns.

---

## 6. Use Diff‑Based Corrections

Feed the AI **only the diff** and the error message.

Tell it:  
> Fix ONLY the diff. Do not rewrite the file.

This prevents regressions, hallucinated rewrites, and invented APIs.

---

## 7. You Define Project Structure

AI writes **only file contents**, never the structure.  
Prevents imaginary folders, wrong import paths, and phantom modules.

---

## 8. Run Real Tests Last

By the time real tests run, ~70% of AI‑generated errors are already eliminated.

---
