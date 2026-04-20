(* interpreter.ml for PL-026 L2 *)
(* This executable interpreter is the canonical source of truth for the language. *)

exception UndefinedSemantics

(* syntax-conflict language: blocks and declarations are reshaped before execution *)
(* Example: :define name [args] -> becomes an internal function declaration node *)

(* TODO: replace with the real HW3/B-language-derived interpreter body. *)
(* Expected execution path: program.json -> AST -> eval -> output trace *)
