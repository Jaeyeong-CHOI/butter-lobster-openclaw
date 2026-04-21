(* interpreter.ml for PL-027 L3 *)
(* This executable interpreter is the canonical source of truth for the language. *)

exception UndefinedSemantics

(* semantic-conflict language: conditionals execute when condition is FALSE *)
let eval_if cond = not cond

(* TODO: replace with the real HW3/B-language-derived interpreter body. *)
(* Expected execution path: program.json -> AST -> eval -> output trace *)
