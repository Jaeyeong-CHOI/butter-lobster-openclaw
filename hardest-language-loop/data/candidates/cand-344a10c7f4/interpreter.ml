(* interpreter.ml for PL-025 L1 *)
(* This executable interpreter is the canonical source of truth for the language. *)

exception UndefinedSemantics

(* token-conflict language: conflicting keywords are normalized before evaluation *)
let normalize_keyword k = match k with | "fn" -> "def" | "unless" -> "if" | _ -> k

(* TODO: replace with the real HW3/B-language-derived interpreter body. *)
(* Expected execution path: program.json -> AST -> eval -> output trace *)
