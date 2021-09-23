# Casts

Casts（译者注：实在没有找到合适的中文表述）是强转的超集：每个强转都可以通过 cast 来明确调用。然而，有些转换需要 cast。虽然强转是普遍存在的，而且基本上是无害的，但是这些“真正的 cast”是罕见的，而且有潜在的危险。因此，必须使用`as`关键字来明确调用 cast：`expr as Type`。

你可以在《The Reference》中找到一个[所有真正的 cast ][cast list]和[ cast 语义][semantics list]的详尽列表。

## Casting 的安全性

真正的 cast 通常围绕着原始指针和原始数字类型。尽管它们很危险，但这些转换在运行时是不会出错的。如果一个 cast 触发了一些微妙的边界条件，也不会有任何迹象表明发生了这种情况，cast 会成功。也就是说，cast 必须在类型的级别上有效，否则会在编译时被静态地阻止。例如，`7u8 as bool`编译会出错。

也就是说， cast 并不是`unsafe`的，因为它们*本身*通常不会违反内存安全。例如，将一个整数转换为一个原始指针很容易导致可怕的事情，然而，创建指针的行为本身是安全的，因为实际使用一个原始指针已经被标记为`unsafe`。

## 一些关于 cast 的说明

### cast raw slice 时的长度问题

请注意，在 cast raw slice 时，长度不会被调整：`*const [u16] as *const [u8]`创建的 slice 只包括原始内存的一半。

### 传递性

Casting 不是递归的，也就是说，即使`e as U1 as U2`是一个有效的表达式，`e as U2`也不一定是。

[cast list]: https://doc.rust-lang.org/reference/expressions/operator-expr.html#type-cast-expressions
[semantics list]: https://doc.rust-lang.org/reference/expressions/operator-expr.html#semantics
