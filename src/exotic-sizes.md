# 非正常大小的类型

大多数的时候，我们期望类型在编译时能够有一个静态已知的非零大小，但这并不总是 Rust 的常态。

## Dynamically Sized Types (DSTs)

Rust 支持动态大小的类型（DST）：这些类型没有静态（编译时）已知的大小或者布局。从表面上看这有点离谱：Rust *必须*知道一个东西的大小和布局，才能正确地进行处理。从这个角度上看，DST 不是一个普通的类型，因为它们没有编译时静态可知的大小，它们只能存在于一个指针之后。任何指向 DST 的指针都会变成一个包含了完善 DST 类型信息的胖指针（详情见下方）。

Rust 暴露了两种主要的 DST 类型：

* trait objects：`dyn MyTrait`
* slices：[`[T]`][slice]、[`str`]及其他

Trait 对象代表某种类型，实现了它所指定的 Trait。确切的原始类型被*删除*，以利于运行时的反射，其中包含使用该类型的所有必要信息的 vtable。补全 Trait 对象指针所需的信息是 vtable 指针，被指向的对象的运行时的大小可以从 vtable 中动态地获取。

一个 slice 只是一些只读的连续存储——通常是一个数组或`Vec`。补全一个 slice 指针所需的信息只是它所指向的元素的数量，指针的运行时大小只是静态已知元素的大小乘以元素的数量。

结构实际上可以直接存储一个 DST 作为其最后一个字段，但这也会使它们自身成为一个 DST：

```rust
// 不能直接存储在栈上
struct MySuperSlice {
    info: u32,
    data: [u8],
}
```

如果这样的类型没有方法来构造它，那么它在很大程度上来看是没啥用的。目前，唯一支持的创建自定义 DST 的方法是使你的类型成为泛型，并执行*非固定大小转换（unsizing coercion）*：

```rust
struct MySuperSliceable<T: ?Sized> {
    info: u32,
    data: T,
}

fn main() {
    let sized: MySuperSliceable<[u8; 8]> = MySuperSliceable {
        info: 17,
        data: [0; 8],
    };

    let dynamic: &MySuperSliceable<[u8]> = &sized;

    // 输出: "17 [0, 0, 0, 0, 0, 0, 0, 0]"
    println!("{} {:?}", dynamic.info, &dynamic.data);
}
```

（是的，自定义 DST 目前仅仅是一个基本半成品的功能。）

## 零大小类型 (ZSTs)

Rust 也允许类型指定他们不占空间：

```rust
struct Nothing; // 无字段意味着没有大小

// 所有字段都无大小意味着整个结构体无大小
struct LotsOfNothing {
    foo: Nothing,
    qux: (),      // 空元组无大小
    baz: [u8; 0], // 空数组无大小
}
```

就其本身而言，零尺寸类型（ZSTs）由于显而易见的原因是相当无用的。然而，就像 Rust 中许多奇怪的布局选择一样，它们的潜力在通用语境中得以实现。在 Rust 中，任何产生或存储 ZST 的操作都可以被简化为无操作（no-op）。首先，存储它甚至没有意义——它不占用任何空间。另外，这种类型的值只有一个，所以任何加载它的操作都可以直接凭空产生它——这也是一个无操作（no-op），因为它不占用任何空间。

这方面最极端的例子之一是 Set 和 Map。给定一个`Map<Key, Value>`，通常可以实现一个`Set<Key>`，作为`Map<Key, UselessJunk>`的一个薄封装。在许多语言中，这将需要为无用的封装分配空间，并进行存储和加载无用封装的工作，然后将其丢弃。对于编译器来说，证明这一点是不必要的，是一个困难的分析。

然而在 Rust 中，我们可以直接说`Set<Key> = Map<Key, ()>`。现在 Rust 静态地知道每个加载和存储都是无用的，而且没有分配有任何大小。其结果是，单例化的代码基本上是 HashSet 的自定义实现，而没有 HashMap 要支持值所带来的开销。

安全的代码不需要担心 ZST，但是*不安全的*代码必须小心没有大小的类型的后果。特别是，指针偏移是无操作的，而分配器通常[需要一个非零的大小][alloc]。

请注意，对 ZST 的引用（包括空片），就像所有其他的引用一样，必须是非空的，并且适当地对齐。解引用 ZST 的空指针或未对齐指针是[未定义的行为][ub]，就像其他类型的引用一样。

[alloc]: https://doc.rust-lang.org/std/alloc/trait.GlobalAlloc.html#tymethod.alloc
[ub]: what-unsafe-does.html

## 空类型

Rust 还允许声明*不能被实例化*的类型。这些类型只能在类型层讨论，而不能在值层讨论。空类型可以通过指定一个没有变体的枚举来声明：

```rust
enum Void {} // 没有变量 = 空类型
```

空类型甚至比 ZST 更加边缘化。空类型的主要作用是为了让某个类型不可达。例如，假设一个 API 需要在一般情况下返回一个结果，但一个特定的情况实际上是不可能的。实际上可以通过返回一个`Result<T, Void>`来在类型级别上传达这个信息。API 的消费者可以放心地 unwrap 这样一个结果，因为他们知道这个值在本质上不可能是`Err`，因为这需要提供一个`Void`类型的值。

原则上，Rust 可以基于这个事实做一些有趣的分析和优化，例如，`Result<T, Void>`只表示为`T`，因为`Err`的情况实际上并不存在（严格来说，这只是一种优化，并不保证，所以例如将一个转化为另一个仍然是 UB）。

比如以下的例子，*曾经*是可以编译成功的：

```rust,compile_fail
enum Void {}

let res: Result<u32, Void> = Ok(0);

// 不存在 Err 的情况，所以 Ok 实际上永远都能匹配成功
let Ok(num) = res;
```

但现在，已经不让这么玩儿了。

关于空类型的最后一个微妙的细节是，构造一个指向它们的原始指针实际上是有效的，但对它们的解引用是未定义行为，因为那是没有意义的。

我们建议不要用`*const Void`来模拟 C 的`void*`类型。很多人之前这样做，但很快就遇到了麻烦，因为 Rust 没有任何安全防护措施来防止用不安全的代码来实例化空类型，如果你这样做了，就是未定义行为。因为开发者有将原始指针转换为引用的习惯，而构造一个`&Void`*也*是未定义行为，所以这尤其成问题。

`*const ()`（或等价物）对`void*`来说效果相当好，可以做成引用而没有任何安全问题。它仍然不能阻止你试图读取或写入数值，但至少它可以编译成一个 no-op 而不是 UB。

## 外部类型

有一个[已被接受的 RFC][extern-types] 来增加具有未知大小的适当类型，称为 *extern 类型*，这将让 Rust 开发人员更准确地模拟像 C 的`void*`和其他“声明但从未定义”的类型。然而，截至 Rust 2018，[该功能在`size_of_val::<MyExternType>()`应该如何表现方面遇到了一些问题][extern-types-issue]。

[extern-types]: https://github.com/rust-lang/rfcs/blob/master/text/1861-extern-types.md
[extern-types-issue]: https://github.com/rust-lang/rust/issues/43467
[`str`]: https://doc.rust-lang.org/std/primitive.str.html
[slice]: https://doc.rust-lang.org/std/primitive.slice.html
