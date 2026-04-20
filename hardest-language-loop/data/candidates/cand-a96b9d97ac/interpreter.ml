(* interpreter.ml for PL-024 L5 *)
(* This executable interpreter is the canonical source of truth for the language. *)

exception UndefinedSemantics

(* compound conflict: keyword remap + syntax reshape + inverted conditionals *)
let normalize_keyword k = match k with | "fn" -> "def" | "give" -> "return" | _ -> k
let eval_if cond = not cond

(* TODO: replace with the real HW3/B-language-derived interpreter body. *)
(* Expected execution path: program.json -> AST -> eval -> output trace *)
