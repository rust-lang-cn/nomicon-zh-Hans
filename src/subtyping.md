# 子类型化和变异性

Rust 使用生命周期来追踪借用和所有权。
但是，原生的生命周期实现可能过于严格，或者会允许未定义行为。

为了实现对生命周期的灵活使用并防止滥用，Rust 使用 **子类型** 和 **变异**。

让我们从一个例子开始。

```rust
// 注意：debug 需要两个具有相同生命周期的参数
fn debug<'a>(a: &'a str, b: &'a str) {
    println!("a = {a:?} b = {b:?}");
}

fn main() {
    let hello: &'static str = "hello";
    {
        let world = String::from("world");
        let world = &world; // 'world 的生命周期比 'static 短
        debug(hello, world);
    }
}
```

在一个保守的生命周期实现中，由于 `hello` 和 `world` 有不同的生命周期，我们可能会看到以下错误：

```text
error[E0308]: mismatched types
 --> src/main.rs:10:16
   |
10 |         debug(hello, world);
   |                      ^
   |                      |
   |                      expected `&'static str`, found struct `&'world str`
```

这是相当不幸的。在这种情况下，我们希望接受的类型的生命周期至少要和 `'world` 一样长。
让我们尝试使用生命周期进行子类型化。

## 子类型化

子类型化是指一种类型可以替代另一种类型的概念。

我们定义 `Sub` 是 `Super` 的子类型（在本章中我们将其表示为 `Sub <: Super`）。

这表示生命周期 `Sub` 的范围要包含 `Super` 的范围，并且 `Sub` 的范围有可能更大。

现在，为了使生命周期子类型化，我们需要先定义一个生命周期：

> `'a` 定义了一段代码区域。

然后我们就可以定义它们之间的关系：

> 当且仅当 `'long` 是一个 **完全包含** `'short` 的代码区域时，`'long <: 'short`。

`'long` 可能定义了一个比 `'short` 更大的区域，但这仍符合我们的定义。

> 虽然在本章后面，子类型化比这要复杂和微妙得多，但这个简单的规则在大多数情况下都适用。除非您编写不安全的代码，否则编译器将为您自动处理所有的特殊情况。

> 但这是 Rustonomicon。我们正在编写不安全的代码，所以我们需要了解这些东西是如何真正工作的，以及我们如何搞乱它。

回到我们上面的例子，我们可以说 `'static` 是 `'world` 的子类型，而又因为生命周期可以通过引用传递（更多内容请参见 [变异性](#变异性)），所以`&'static str` 是 `&'world str` 的子类型，通过下文讲述的 _变异性_ 我们可以将 `&'static str` 的生命周期收缩为 `&'world str`。如此，上面的示例可以编译：

```rust
fn debug<'a>(a: &'a str, b: &'a str) {
    println!("a = {a:?} b = {b:?}");
}

fn main() {
    let hello: &'static str = "hello";
    {
        let world = String::from("world");
        let world = &world; // 'world 的生命周期比 'static 短
        debug(hello, world); // hello 从 `&'static str` 静默收缩为 `&'world str`
    }
}
```

## 变异性

在上面，我们简单地说明了 `'static <: 'b` 静默地暗示了 `&'static T <: &'b T` 。这使用了一个名为 _变异_ 的性质。然而，这并不总是像这个例子那样简单。为了理解这一点，让我们尝试稍微改变这个例子：

```rust, compile_fail, E0597
fn assign<T>(input: &mut T, val: T) {
    *input = val;
}

fn main() {
    let mut hello: &'static str = "hello";
    {
        let world = String::from("world");
        assign(&mut hello, &world);
    }
    println!("{hello}"); // 使用在被释放后的值 😿
}
```

在 `assign` 中，我们将 `hello` 引用设置为指向 `world`。
但是 `world` 在 `println` 使用 `hello` 之前就已经超出了作用域！

这是一个典型的在释放后使用错误！

我们第一反应可能是怪 `assign` 的实现，但实际上这里并没有什么错误。一个值想要赋值到一个具有相同类型的 `T` 也不奇怪。

所以，问题在于，我们不能假设 `&mut &'static str` 也可以转换成 `&mut &'b str`。
这意味着，即使 `'static` 是 `'b` 的子类型，`&mut &'static str` 也 **不能** 是 `&mut &'b str` 的子类型。

**变异性** 是 Rust 引用通过它们的泛型参数，来定义引用之间的子类型关系。

> 注意：为了方便起见，我们将定义一个泛型类型 `F<T>`，以便我们可以方便地讨论 `T`。希望这在上下文中是清楚的。

类型 `F` 的 *变异性* 代表了其输入子类型如何影响其输出子类型。

在 Rust 中有三种变异性，假设 `Sub` 是 `Super` 的子类型：

* `F` 是 **协变的**，如果 `F<Sub>` 是 `F<Super>` 的子类型（子类型属性被传递）(译者注：这里被传递的意思是尖括号里面的子类型关系(`Sub <: Super`)被传递到尖括号外(`F<Sub> <: F<Super>`))
* `F` 是 **逆变的**，如果 `F<Super>` 是 `F<Sub>` 的子类型（子类型属性被 "反转"）(译者注：即尖括号里面的子类型关系(`Sub <: Super`)在尖括号外面被反转(`F<Super> <: F<Sub>`))
* 否则，`F` 是 **不变的** （不存在子类型关系）(译者注：即尖括号里面的子类型关系不会影响尖括号外面的子类型关系)

让我们回想上面的例子，如果 `'a` 是 `'b` 的子类型，我们可以将 `&'a T` 视作是 `&'b T` 的子类型，因而`&'a T`对于 `'a` 上是协变的。

此外，我们注意到不能将 `&mut &'a U` 视为 `&mut &'b U` 的子类型，因此我们可以说 `&mut T` 在 `T` 上是 *不变的*

以下是一些其他泛型类型的变异性的表格：

|                 |     'a    |         T         |     U     |
|-----------------|:---------:|:-----------------:|:---------:|
| `&'a T `        | 协变     | 协变             |           |
| `&'a mut T`     | 协变     | 不变             |           |
| `Box<T>`        |           | 协变             |           |
| `Vec<T>`        |           | 协变             |           |
| `UnsafeCell<T>` |           | 不变             |           |
| `Cell<T>`       |           | 不变             |           |
| `fn(T) -> U`    |           | **逆变**         | 协变     |
| `*const T`      |           | 协变             |           |
| `*mut T`        |           | 不变             |           |

其中，一些类型的变异性可以直接类比成其他类型。

* `Vec<T>` 以及所有其他占有所有权的集合遵循与 `Box<T>` 相同的逻辑
* `Cell<T>` 以及所有其他内部可变性类型遵循与 `UnsafeCell<T>` 相同的逻辑
* 具有内部可变性的 `UnsafeCell<T>` 使其具有与 `&mut T` 相同的变异性属性 (译者注：因为具有内部可变性的`UnsafeCell<T>` `Cell<T>`等，都可以通过仅仅使用 `&T` 进行 `&mut T` 才能进行的操作，所以它们必须和 `&mut T` 一样是不变的)
* `*const T` 遵循 `&T` 的逻辑
* `*mut T` 遵循 `&mut T`（或 `UnsafeCell<T>`）的逻辑

有关其他类型，请参见[参考手册的 "变异性" 部分][variance-table]。

[variance-table]: ../reference/subtyping.html#variance

> 注意：语言中唯一的逆变来源于函数参数，这就是为什么它实际上在实践中很少出现。调用逆变涉及到函数指针的高阶编程，这些函数指针需要具有特定生命周期（而不是通常的 "任意生命周期"）的引用，而这将涉及更高级别的生命周期，它们可以独立于子类型化工作。

现在我们对变异性有了更深入的理解，让我们更详细地讨论一些例子。

```rust,compile_fail,E0597
fn assign<T>(input: &mut T, val: T) {
    *input = val;
}

fn main() {
    let mut hello: &'static str = "hello";
    {
        let world = String::from("world");
        assign(&mut hello, &world);
    }
    println!("{hello}");
}
```

运行这个例子会得到什么？

```text
error[E0597]: `world` does not live long enough
  --> src/main.rs:9:28
   |
6  |     let mut hello: &'static str = "hello";
   |                    ------------ type annotation requires that `world` is borrowed for `'static`
...
9  |         assign(&mut hello, &world);
   |                            ^^^^^^ borrowed value does not live long enough
10 |     }
   |     - `world` dropped here while still borrowed
```

很好，它不能编译！让我们详细了解这里发生了什么。

首先让我们看下 `assign` 函数：

```rust
fn assign<T>(input: &mut T, val: T) {
    *input = val;
}
```

它只是接收一个可变引用和一个值，然后将该值覆盖。这个函数的关键在于它在签名中清楚地说，被引用和值必须是 *完全相同* 的类型。

与此同时，在调用者中，我们传入 `&mut &'static str` 和 `&'world str`。

由于 `&mut T` 在 `T` 上是不变的，所以编译器得出结论，它不能对第一个参数应用任何子类型化，因此 `T` 必须是 `&'static str`。

这与 `&T` 情况相反：

```rust
fn debug<T: std::fmt::Debug>(a: T, b: T) {
    println!("a = {a:?} b = {b:?}");
}
```

尽管 `a` 和 `b` 必须具有相同的类型 `T`，但由于 `&'a T` 在 `'a` 上是协变的，我们可以执行子类型化。因此，编译器认为，当且仅当 `&'static str` 是 `&'b str` 的子类型时（这种关系在 `'static <: 'b` 时成立），`&'static str` 才可以变为 `&'b str`。这是正确的，因此编译器很乐意继续编译这段代码。

事实证明，Box（以及 Vec，HashMap 等）协变的原因与生命周期协变的原因相似：只要你尝试将它们放入诸如可变引用之类的东西中，就会继承不变性，从而阻止你做任何坏事。

然而，Box 使我们更容易关注值传递的引用问题，我们之前部分忽略了这一点。

与许多允许值在任何时候被自由别名的语言不同，Rust 有一个非常严格的规则：如果您可以修改或移动一个值，那么您必须确保是唯一一个可以访问该值的人(译者注：即拥有该值的所有权)。

考虑以下代码：

```rust,ignore
let hello: Box<&'static str> = Box::new("hello");

let mut world: Box<&'b str>;
world = hello;
```

我们已经忘记了 `hello` 的 `'static` 生命周期也没有任何问题，因为当我们将 `hello` 移动到了一个只知道它的生命周期为 `'b` 的变量时，**我们销毁了唯一记住它生命周期为`'static`的东西！我们不再需要 `hello` 的生命周期更长了！**

现在还剩一件事要解释：函数指针。

要了解为什么 `fn(T) -> U` 应该在 `U` 上是协变的，请思考一下这个签名：

<!-- ignore: 简化代码 -->
```rust,ignore
fn get_str() -> &'a str;
```

该函数声明可以生成一个由某个生命周期 `'a` 绑定的 `str`。类似地，我们可以使用以下签名来定义一个函数：

<!-- ignore: 简化代码 -->
```rust,ignore
fn get_static() -> &'static str;
```

所以当函数被调用时，它只期望一个生命周期至少为 `'a` 的 `&str` 的值，至于这个值的生命周期是不是比 `'a` 更长，并不重要。

然而，相同的逻辑不能应用于*函数参数*。思考一下：

<!-- ignore: 简化代码 -->
```rust,ignore
fn store_ref(&'a str);
```

和

<!-- ignore: 简化代码 -->
```rust,ignore
fn store_static(&'static str);
```

第一个函数可以接受任何字符串引用，只要它的生命周期包含 `'a`，但第二个函数不能接受一个生命周期小于 `'static` 的字符串引用，这将导致冲突。变异性不适用于此。但是，如果我们将其反过来，实际上*确实*行得通！如果我们需要一个可以处理 `&'static str` 的函数，一个可以处理*任意*引用生命周期的函数肯定可以很好地工作。

让我们看看实践中的例子

```rust, compile_fail
thread_local! {
    pub static StaticVecs: RefCell<Vec<&'static str>> = RefCell::new(Vec::new());
}

/// 将给定的输入保存到一个thread local的 `Vec<&'static str>`
fn store(input: &'static str) {
    StaticVecs.with_borrow_mut(|v| v.push(input));
}

/// 用有着相同生命周期的参数 `input` 去调用给定的函数
fn demo<'a>(input: &'a str, f: fn(&'a str)) {
    f(input);
}

fn main() {
    demo("hello", store); // "hello" 是 'static。可以正常调用 `store`

    {
        let smuggle = String::from("smuggle");

        // `&smuggle` 的生命周期并非· `'static`。
        // 如果我们用 `&smuggle` 调用 `store`，
        // 我们将把一个无效的生命周期推入 `StaticVecs`。
        // 因此，`fn(&'static str)` 不能是 `fn(&'a str)` 的子类型
        demo(&smuggle, store);
    }

    // use after free 😿
    StaticVecs.with_borrow(|v| println!("{v:?}"));
}
```

这就是为什么函数类型，与语言中的其他内容不同，是*逆变*的。

现在，你对于标准库提供的类型的变异性应有了充分的理解，但是如何确定*您*定义的类型的变异性呢？ 不太规范地说，结构体继承了其字段的变异性。如果一个结构体 `MyType` 有一个泛型参数 `A`，并且在字段 `a` 中使用了 `A`，那么 MyType 对 `A` 的变异性与 `a` 对 `A` 的变异性完全相同。

然而，如果 `A` 被多个字段使用：

* 如果 `A` 的所有用途都是协变的，则 MyType 在 `A` 上是协变的
* 如果 `A` 的所有用途都是逆变的，则 MyType 在 `A` 上是逆变的
* 否则，MyType 在 `A` 上是不变的

```rust
use std::cell::Cell;

struct MyType<'a, 'b, A: 'a, B: 'b, C, D, E, F, G, H, In, Out, Mixed> {
    a: &'a A,     // 对 'a 和 A 是协变的
    b: &'b mut B, // 对 'b 是协变的，对 B 是不变的

    c: *const C,  // 对 C 是协变的
    d: *mut D,    // 对 D 是不变的

    e: E,         // 对 E 是协变的
    f: Vec<F>,    // 对 F 是协变的
    g: Cell<G>,   // 对 G 是不变的

    h1: H,        // 本来也会对 H 是协变的，但...
    h2: Cell<H>,  // 对 H 是不变的，因为不变性在所有冲突中都是胜利者

    i: fn(In) -> Out,       // 对 In 是逆变的，对 Out 是协变的

    k1: fn(Mixed) -> usize, // 本来会对 Mixed 是逆变的，但...
    k2: Mixed,              // 对 Mixed 是不变的，因为不变性在所有冲突中都是胜利者
}
```

现在你对 Rust 中的子类型和变异性概念应该有了更深入的理解。尽管本章涵盖了许多概念，但通过编译器和类型系统所提供的严密检查来确保这些规则得到遵循和安全操作。当编写泛型代码时，要确保您正确理解子类型化和变异性，以避免出现意外错误和潜在安全问题。
