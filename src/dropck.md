# 丢弃检查

我们已经看到了生命周期如何为我们提供了一些相当简单的规则来确保我们永远不会读到悬空的引用。但是到目前为止， _outlives_ 是一种包容的关系。也就是说，当我们谈论`'a: 'b`时，`'a`可以和`'b`的寿命一样长。乍一看，这似乎是一个无意义的特点。没有什么东西会和另一个东西同时被丢弃，对吗？这就是为什么我们对以下`let`语句解语法糖：

<!-- ignore: simplified code -->

```rust,ignore
let x;
let y;
```

解语法糖：

<!-- ignore: desugared code -->

```rust,ignore
{
    let x;
    {
        let y;
    }
}
```

有一些更复杂的情况不可能用作用域来解语法糖，但顺序是被定义好的——变量按其定义的相反顺序丢弃，结构体和元组的字段按其定义的顺序丢弃。在 [RFC 1857][rfc1857] 中有一些关于丢弃顺序的更多细节。

让我们来试试：

<!-- ignore: simplified code -->

```rust,ignore
let tuple = (vec![], vec![]);
```

左边的 Vec 先被丢弃。但这是否意味着在借用检查器的眼中，右边 Vec 一定活得更长？这个问题的答案是 _No_。借用检查器可以分别跟踪元组的字段，但它仍然无法知道 哪个Vec 元素活得更久，因为 Vec 元素是通过借用检查器不理解的纯库代码手动丢弃的。

那么，我们为什么要关心呢？是因为如果类型系统不小心，它可能会意外地产生悬空指针。比如下面这个简单的程序：

```rust
struct Inspector<'a>(&'a u8);

struct World<'a> {
    inspector: Option<Inspector<'a>>,
    days: Box<u8>,
}

fn main() {
    let mut world = World {
        inspector: None,
        days: Box::new(1),
    };
    world.inspector = Some(Inspector(&world.days));
}
```

这个程序看起来很合理，而且可以编译。事实上，`days`的寿命并没有严格地超过`inspector`的寿命，这并不重要。只要`inspector`还活着，`days`也会活着。

然而，如果我们添加一个析构器，程序就不会再编译了!

```rust,compile_fail
struct Inspector<'a>(&'a u8);

impl<'a> Drop for Inspector<'a> {
    fn drop(&mut self) {
        println!("I was only {} days from retirement!", self.0);
    }
}

struct World<'a> {
    inspector: Option<Inspector<'a>>,
    days: Box<u8>,
}

fn main() {
    let mut world = World {
        inspector: None,
        days: Box::new(1),
    };
    world.inspector = Some(Inspector(&world.days));
    // 如果 `days` 碰巧在这里被析构了，然后 Inspector 才被析构，就会造成`内存释放后读取`的问题！
}
```

```text
error[E0597]: `world.days` does not live long enough
  --> src/main.rs:19:38
   |
19 |     world.inspector = Some(Inspector(&world.days));
   |                                      ^^^^^^^^^^^ borrowed value does not live long enough
...
22 | }
   | -
   | |
   | `world.days` dropped here while still borrowed
   | borrow might be used here, when `world` is dropped and runs the destructor for type `World<'_>`
```

你可以尝试改变字段的顺序，或者用一个元组来代替struct，但还是不能编译。

实现`Drop`可以让`Inspector`在被丢弃时执行一些代码。使得它有可能观察到那些本该和它生命周期一样长的类型实际上是先被销毁的。

有趣的是，只有泛型需要担心这个问题。如果它们不是泛型的，那么它们唯一能承载的寿命就是`'static`，它将真正地一直活着。这就是为什么这个问题被称为 _sound generic drop_。健壮的泛型丢弃是由 _drop checker_ 强制执行的。截止到本文写作时，关于丢弃检查器（也被称为`dropck`）如何验证类型的一些更细微的细节还完全是未知数。然而，“大规则”是我们这一节所关注的微妙之处：

**对于一个泛型类型来说，要健壮地实现 drop，其泛型参数必须严格超过它的寿命。**

遵守这一规则（通常）是满足借用检查器的必要条件；遵守这一规则是健壮地泛型丢弃的充分不必要条件。即如果你的类型遵守了这个规则，那么它的 drop 肯定是健壮的。

不一定要满足上述规则的原因是，有些 Drop 实现不会访问借用的数据，即使他们的类型给了他们这种访问的能力，或者因为我们知道具体的 Drop 顺序，且借用的数据依旧完好，即使借用检查器不知道。

例如，上述`Inspector`例子的这个变体永远不会访问借来的数据：

```rust,compile_fail
struct Inspector<'a>(&'a u8, &'static str);

impl<'a> Drop for Inspector<'a> {
    fn drop(&mut self) {
        println!("Inspector(_, {}) knows when *not* to inspect.", self.1);
    }
}

struct World<'a> {
    inspector: Option<Inspector<'a>>,
    days: Box<u8>,
}

fn main() {
    let mut world = World {
        inspector: None,
        days: Box::new(1),
    };
    world.inspector = Some(Inspector(&world.days, "gadget"));
    // 假设 `days` 刚好在这里析构了，
    // 并且假设析构函数可以确保：该函数确保不会访问对 `days` 的引用
}
```

同样地，下面这个变体也不会访问借来的数据：

```rust,compile_fail
struct Inspector<T>(T, &'static str);

impl<T> Drop for Inspector<T> {
    fn drop(&mut self) {
        println!("Inspector(_, {}) knows when *not* to inspect.", self.1);
    }
}

struct World<T> {
    inspector: Option<Inspector<T>>,
    days: Box<u8>,
}

fn main() {
    let mut world = World {
        inspector: None,
        days: Box::new(1),
    };
    world.inspector = Some(Inspector(&world.days, "gadget"));
    // 假设 `days` 刚好在这里析构了，
    // 并且假设析构函数可以确保：该函数确保不会访问对 `days` 的引用
}
```

然而，上述两种变体在分析`fn main`时都被借用检查器拒绝了，说`days`的生命周期不够长。

原因是对`main`的借用检查分析时，借用检查器并不了解每个`Inspector`的`Drop`实现的内部情况。就借用检查器在分析`main`时知道的情况来看，检查器的析构器主体可能会访问这些借用的数据。

因此，丢弃检查器强迫一个值中的所有借用数据的生命周期严格地超过该值的生命周期。

## 一种逃逸方法

丢弃检查的精确规则在未来可能会减少限制。

目前的分析是故意保守和琐碎的；它强制一个值中的所有借来的数据的生命周期超过该值的生命周期，这当然是合理的。

未来版本的语言可能会使分析更加精确，以减少正确代码被拒绝为不安全的情况。这将有助于解决诸如上述两个`Inspector`知道在销毁时不访问借来的数据的情况。

但与此同时，有一个不稳定的属性，可以用来断言（不安全的）泛型的析构器 _保证_ 不访问任何失效数据，即使它的类型赋予它这样的能力。

这个属性被称为`may_dangle`，是在[RFC1327][rfc1327]中引入的。要在上面的`Inspector`上用上它，我们可以这么写：

```rust
#![feature(dropck_eyepatch)]

struct Inspector<'a>(&'a u8, &'static str);

unsafe impl<#[may_dangle] 'a> Drop for Inspector<'a> {
    fn drop(&mut self) {
        println!("Inspector(_, {}) knows when *not* to inspect.", self.1);
    }
}

struct World<'a> {
    days: Box<u8>,
    inspector: Option<Inspector<'a>>,
}

fn main() {
    let mut world = World {
        inspector: None,
        days: Box::new(1),
    };
    world.inspector = Some(Inspector(&world.days, "gadget"));
}
```

使用这个属性需要将`Drop`标记为`unsafe`，因为编译器没有检查隐含的断言，即没有访问潜在的失效数据（例如上面的`self.0`）。

该属性可以应用于任何数量的生命周期和类型参数。在下面的例子中，我们断言我们没有访问寿命为`'b`的引用后面的数据，并且`T`的唯一用途是 move 或 drop，但是从`'a`和`U`中省略了该属性，因为我们确实访问具有该生命周期和该类型的数据。

```rust
#![feature(dropck_eyepatch)]
use std::fmt::Display;

struct Inspector<'a, 'b, T, U: Display>(&'a u8, &'b u8, T, U);

unsafe impl<'a, #[may_dangle] 'b, #[may_dangle] T, U: Display> Drop for Inspector<'a, 'b, T, U> {
    fn drop(&mut self) {
        println!("Inspector({}, _, _, {})", self.0, self.3);
    }
}
```

有时很明显，不可能发生这样的访问，比如上面的情况。然而，当处理一个通用类型的参数时，这种访问可能会间接地发生，这种间接访问的例子是：

- 调用一个回调
- 通过 trait 方法调用

（未来对语言的修改，如 impl 的特化，可能会增加这种间接访问的其他途径。）

下面是一个回调的例子：

```rust
struct Inspector<T>(T, &'static str, Box<for <'r> fn(&'r T) -> String>);

impl<T> Drop for Inspector<T> {
    fn drop(&mut self) {
        // 如果 `T` 是 `&'a _` 这种类型，那么 self.2 有可能访问了被引用的变量
        println!("Inspector({}, {}) unwittingly inspects expired data.",
                 (self.2)(&self.0), self.1);
    }
}
```

下面是一个通过 trait 方法调用的例子：

```rust
use std::fmt;

struct Inspector<T: fmt::Display>(T, &'static str);

impl<T: fmt::Display> Drop for Inspector<T> {
    fn drop(&mut self) {
        // 这里可能隐藏了一个对于 `<T as Display>::fmt` 的调用,
        // 如果 `T` 是 `&'a _` 这种类型，就可能访问了借用的变量
        println!("Inspector({}, {}) unwittingly inspects expired data.",
                 self.0, self.1);
    }
}
```

当然，所有这些访问都可以进一步隐藏在由析构器调用的一些其他方法中，而不是直接写在析构器中。

在上述所有在析构器中访问`&'a u8`的情况下，添加`#[may_dangle]`属性使得该类型容易被误用，而借用检查器不会发现，从而导致问题。所以最好不要添加这个属性。

## 关于丢弃顺序的附带说明

虽然结构内部字段的删除顺序是被定义的，但对它的依赖是脆弱而微妙的。当顺序很重要时，最好使用[`ManuallyDrop`]包装器。

## 这就是关于丢弃检查器的全部内容吗？

事实证明，在编写不安全的代码时，我们通常根本不需要担心为丢弃检查器做正确的事情。然而，有一种特殊情况是需要担心的，我们将在下一节看一下。

[rfc1327]: https://github.com/rust-lang/rfcs/blob/master/text/1327-dropck-param-eyepatch.md
[rfc1857]: https://github.com/rust-lang/rfcs/blob/master/text/1857-stabilize-drop-order.md
[`manuallydrop`]: https://doc.rust-lang.org/std/mem/struct.ManuallyDrop.html
