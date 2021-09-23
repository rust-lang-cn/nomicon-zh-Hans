# 生命周期

Rust 通过*生命周期*来执行相关的规则。生命周期是指一个引用必须有效的代码区域，这些区域可能相当复杂，因为它们对应着程序中的执行路径。这些执行路径中甚至可能存在漏洞，因为只要在再次使用引用之前对其进行重新初始化，就有可能使其失效。包含引用（或假装包含）的类型也可以用生命周期来标记，这样 Rust 就可以防止它们也被失效。

在我们大多数例子中，生命周期将与作用域重合，这是因为我们的例子很简单。下面将介绍它们不重合的更复杂的情况。

在一个函数体中，Rust 通常不需要你明确地命名所涉及的生命周期。这是因为一般来说，在本地环境中谈论生命周期是没有必要的；Rust 拥有所有的信息，并且可以尽可能地以最佳方式解决所有问题。许多匿名的作用域和暂时性的变量你就必须要写了，不然就不让你代码编译通过。

然而，一旦你跨越了函数的边界，你就需要开始考虑生命周期了。生命周期是用撇号表示的：`'a`、`'static`。为了尝试使用生命周期，我们将假装我们被允许用生命周期来标记作用域，并尝试手动解一下本章开头例子的语法糖。

我们之前的例子使用了一种*激进*的语法糖——甚至是高果糖玉米糖浆——因为明确地写出所有东西是*非常繁琐*的。所有的 Rust 代码都依赖于积极的推理和对“显而易见”的东西的删除。

一个特别有趣的语法糖是，每个`let`语句都隐含地引入了一个作用域。在大多数情况下，这其实并不重要。然而，这对那些相互引用的变量来说确实很重要。作为一个简单的例子，让我们对这段简单的 Rust 代码进行完全解糖：

```rust
let x = 0;
let y = &x;
let z = &y;
```

借用检查器总是试图最小化生命周期的范围，所以它很可能会脱糖为以下内容：

<!-- ignore: desugared code -->
```rust,ignore
// NOTE: `'a: {` and `&'b x` is not valid syntax!
'a: {
    let x: i32 = 0;
    'b: {
        // lifetime used is 'b because that's good enough.
        let y: &'b i32 = &'b x;
        'c: {
            // ditto on 'c
            let z: &'c &'b i32 = &'c y;
        }
    }
}
```

哇，这真是……太可怕了！让我们花点时间感谢 Rust 让这一切变得简单。

实际上，传递一个引用到外部作用域将导致 Rust 推断出一个更大的生命周期。

```rust
let x = 0;
let z;
let y = &x;
z = y;
```

<!-- ignore: desugared code -->
```rust,ignore
'a: {
    let x: i32 = 0;
    'b: {
        let z: &'b i32;
        'c: {
            // Must use 'b here because this reference is
            // being passed to that scope.
            let y: &'b i32 = &'b x;
            z = y;
        }
    }
}
```

## 例子：超出所有者生命周期的引用

让我们看看之前的那些例子：

```rust,compile_fail
fn as_str(data: &u32) -> &str {
    let s = format!("{}", data);
    &s
}
```

解语法糖后：

<!-- ignore: desugared code -->
```rust,ignore
fn as_str<'a>(data: &'a u32) -> &'a str {
    'b: {
        let s = format!("{}", data);
        return &'a s;
    }
}
```

`as_str`的这个签名接收了一个具有*某个*生命周期的 u32 的引用，并返回一个可以*存活同样长*的 str 的引用。我们已经大致能猜到为什么这个函数签名可能是个麻烦了，这意味着我们将在 u32 的引用所处的范围内找到一个 str，或者*甚至*在更早的地方。这要求有点高。

然后我们继续计算字符串`s`，并返回它的一个引用。由于我们的函数的契约规定这个引用必须超过`'a`，这就是我们推断出的引用的生命周期。不幸的是，`s`被定义在作用域`'b`中，所以唯一合理的方法是`'b`包含`'a`，这显然是错误的，因为`'a`必须包含函数调用本身。因此，我们创建了一个引用，它的生命周期超过了它的引用者，这正是我们所说的引用不能做的第一件事。编译器理所当然地直接报错。

为了更清楚地说明这一点，我们可以扩展这个例子：

<!-- ignore: desugared code -->
```rust,ignore
fn as_str<'a>(data: &'a u32) -> &'a str {
    'b: {
        let s = format!("{}", data);
        return &'a s
    }
}

fn main() {
    'c: {
        let x: u32 = 0;
        'd: {
            // An anonymous scope is introduced because the borrow does not
            // need to last for the whole scope x is valid for. The return
            // of as_str must find a str somewhere before this function
            // call. Obviously not happening.
            println!("{}", as_str::<'d>(&'d x));
        }
    }
}
```

当然，这个函数的正确写法是这样的：

```rust
fn to_string(data: &u32) -> String {
    format!("{}", data)
}
```

我们必须在函数里面产生一个拥有所有权的值才能返回! 我们唯一可以返回一个`&'a str`的方法是，它在`&'a u32`的一个字段中，但显然不是这样的。

（实际上我们也可以直接返回一个字符串字面量，作为一个全局的字面量可以被认为是在堆栈的底部；尽管这对我们的实现*有一点*限制）。

## 示例：别名一个可变引用

来看另一个例子：

```rust,compile_fail
let mut data = vec![1, 2, 3];
let x = &data[0];
data.push(4);
println!("{}", x);
```

<!-- ignore: desugared code -->
```rust,ignore
'a: {
    let mut data: Vec<i32> = vec![1, 2, 3];
    'b: {
        // 'b is as big as we need this borrow to be
        // (just need to get to `println!`)
        let x: &'b i32 = Index::index::<'b>(&'b data, 0);
        'c: {
            // Temporary scope because we don't need the
            // &mut to last any longer.
            Vec::push(&'c mut data, 4);
        }
        println!("{}", x);
    }
}
```

这里的问题更微妙、更有趣。我们希望 Rust 拒绝这个程序，理由如下：我们有一个存活的共享引用`x`到`data`的一个子集，当我们试图把`data`的可变引用传给`push`时。这将创建一个可变引用的别名，而这将违反引用的*第二条*规则。

然而，这根本不是 Rust 认为这个程序有问题的原因。Rust 不理解`x`是对`data`的一个子集的引用。它根本就不理解`Vec`。它看到的是，`x`必须活着，才能打印出`'b`；并且，`Index::index`的签名要求我们对`data`的引用必须在`'b`中存在。当我们试图调用`push`时，它看到我们试图构造一个`&'c mut data`。Rust 知道`'c`包含在`'b`中，并拒绝了我们的程序，因为`&'b data`必然还存活着！

在这里，我们看到生命周期系统比我们真正感兴趣的引用语义要粗略得多。在大多数情况下，*这完全没问题*，因为它使我们不用花一整天的时间向编译器解释我们的程序。然而，这确实意味着有部分程序对于 Rust 的*真正的*语义来说是完全正确的，但却被拒绝了，因为 lifetime 太傻了。

## 生命周期所覆盖的区域

一个引用（有时称为*borrow*）从它被创建到最后一次使用都是*存活*的。被 borrow 的值的生命周期只需要超过引用的生命周期就行。这看起来很简单，但有一些微妙之处。

下面的代码可以成功编译，因为在打印完`x`之后，它就不再需要了，所以它是悬空的还是别名的都无所谓（尽管变量`x`*技术上*一直存活到作用域的最后）：

```rust
let mut data = vec![1, 2, 3];
let x = &data[0];
println!("{}", x);
// This is OK, x is no longer needed
data.push(4);
```

然而，如果该值有一个析构器，析构器就会在作用域的末端运行。而运行析构器被认为是一种使用——显然是最后一次使用。所以，这将会编译报错：

```rust,compile_fail
#[derive(Debug)]
struct X<'a>(&'a i32);

impl Drop for X<'_> {
    fn drop(&mut self) {}
}

let mut data = vec![1, 2, 3];
let x = X(&data[0]);
println!("{:?}", x);
data.push(4);
// Here, the destructor is run and therefore this'll fail to compile.
```

让编译器相信`x`不再有效的一个方法是在`data.push(4)`之前使用`drop(x)`。

此外，可能会有多种最后一次的引用使用，例如在一个条件的每个分支中：

```rust
# fn some_condition() -> bool { true }
let mut data = vec![1, 2, 3];
let x = &data[0];

if some_condition() {
    println!("{}", x); // This is the last use of `x` in this branch
    data.push(4);      // So we can push here
} else {
    // There's no use of `x` in here, so effectively the last use is the
    // creation of x at the top of the example.
    data.push(5);
}
```

生命周期中可以有暂停，或者你可以把它看成是两个不同的借用，只是被绑在同一个局部变量上。这种情况经常发生在循环周围（在循环结束时写入一个变量的新值，并在下一次迭代的顶部最后一次使用它）。

```rust
let mut data = vec![1, 2, 3];
// This mut allows us to change where the reference points to
let mut x = &data[0];

println!("{}", x); // Last use of this borrow
data.push(4);
x = &data[3]; // We start a new borrow here
println!("{}", x);
```

Rust 曾经一直保持着借用的生命，直到作用域结束，所以这些例子在旧的编译器中可能无法编译。此外，还有一些边界条件，Rust 不能正确地缩短借用的有效部分，即使看起来应该这样做，也不能编译。这些问题将随着时间的推移得到解决。
