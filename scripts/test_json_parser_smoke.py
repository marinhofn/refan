# Script de smoke para testar extract_json_from_text
from src.utils.json_parser import extract_json_from_text

examples = [
    # exemplo com texto antes e depois (similar ao log do usuário)
    '''This diff contains both behavioral and structural modifications to the codebase.

Behavioral changes include:
1. Addition of a new method `getProtocolServiceKey()` in the `RpcInvocation` class, which returns the protocol service key associated with an invocation.
2. Modification of the constructor for `RpcInvocation` to accept a new parameter `protocolServiceKey`.
3. Addition of a new field `protocolServiceKey` in the `RpcInvocation` class to store the protocol service key.
4. Modification of the `setRpcContext()` method in the `RpcContext` class to set the protocol service key when setting the consumer URL.
5. Addition of a new field `protocolServiceKey` in the `Invocation` interface, which is a superinterface for `RpcInvocation`.
6. Modification of the `getProtocolServiceKey()` method in the `Invocation` interface to return the protocol service key associated with an invocation.
7. Addition of a new field `protocolServiceKey` in the `Invoker` class, which is used to store the protoc

{
    "repository": "https://github.com/alibaba/dubbo",
    "commit_hash_before": "3124dd8a",
    "commit_hash_current": "3124dd8a",
    "refactoring_type": "floss",
    "justification": "Changed constructor and added field protocolServiceKey"
}

💾 Falha JSON salva em json_failures.json (total: 237 falhas)
''',

    # exemplo com JSON em bloco de código
    """
Some explanation
```json
{
  "repository": "repo",
  "commit_hash_before": "abc",
  "commit_hash_current": "def",
  "refactoring_type": "pure",
  "justification": "only renames"
}
```
""",

    # exemplo inválido
    "No JSON here, just text and analysis: the changes are purely structural."
]

for i, ex in enumerate(examples, 1):
    print(f"--- Example {i} ---")
    res = extract_json_from_text(ex)
    print(res)
    print()
