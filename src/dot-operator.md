# 点运算符

点运算符将执行很多类型转换的魔法：它将执行自动引用、自动去引用和强制转换，直到类型匹配。方法查找的详细机制定义在[这里][method_lookup]，简要的概述如下：

假设我们有一个函数`foo`，它有一个接收器（一个`self`、`&self`或`&mut self`参数）。如果我们调用`value.foo()`，编译器需要确定`Self`是什么类型，然后才能调用该函数的正确实现。在这个例子中，我们将说`value`具有`T`类型。

我们将使用[full-qualified syntax][fqs]来更清楚地说明我们到底是在哪个类型上调用一个函数。

- 首先，编译器会检查是否可以直接调用`T::foo(value)`。这被称为“按值”方法调用。
- 如果它不能调用这个函数（例如，如果这个函数的类型不对，或者一个 trait 没有为`Self`实现），那么编译器就会尝试添加一个自动引用。这意味着编译器会尝试`<&T>::foo(value)`和`<&mut T>::foo(value)`。这被称为“autoref”方法调用。
- 如果这些候选方法都不奏效，它就对`T`解引用并再次尝试。这使用了`Deref`特性——如果`T: Deref<Target = U>`，那么它就用`U`而不是`T`类型再试。如果它不能解除对`T`的引用，它也可以尝试 _unsizing_`T`。这只是意味着，如果`T`在编译时有一个已知的大小参数，那么在解析方法时它就会“忘记”它。例如，这个 unsizing 步骤可以通过“忘记”数组的大小将`[i32; 2]`转换成`[i32]`。

下面是一个方法查找算法的例子：

```rust,ignore
let array: Rc<Box<[T; 3]>> = ...;
let first_entry = array[0];
```

当数组在这么多的间接点后面时，编译器是如何实际计算`array[0]`的呢？首先，`array[0]`实际上只是[`Index`][index]特性的语法糖——编译器会将`array[0]`转换成`array.index(0)`。现在，编译器检查`array`是否实现了`Index`，这样它就可以调用这个函数。

然后，编译器检查`Rc<Box<[T; 3]>>`是否实现了`Index`，但它没有，`&Rc<Box<[T; 3]>>`和`&mut Rc<Box<[T; 3]>>`也没有。由于这些方法都不起作用，编译器将`Rc<Box<[T; 3]>`解引用到`Box<[T; 3]>`中，并再次尝试。`Box<[T; 3]>`、`&Box<[T; 3]>`和`&mut Box<[T; 3]>`没有实现`Index`，所以它再次解引用。`[T; 3]`和它的自动引用也没有实现`Index`。它不能再继续解引用`[T; 3]`，所以编译器取消了它的大小，得到了`[T]`。最后，`[T]`实现了`Index`，所以它现在可以调用实际的`index`函数。

考虑一下下面这个更复杂的点运算符工作的例子：

```rust
fn do_stuff<T: Clone>(value: &T) {
    let cloned = value.clone();
}
```

实现了`Clone`的是什么类型？首先，编译器检查是否可以按值调用。`value`的类型是`&T`，所以`clone`函数的签名是`fn clone(&T) -> T`。它知道`T: Clone`，所以编译器发现`cloned: T`。

如果取消`T: Clone`的限制，会发生什么？它将不能按值调用，因为`T`没有实现`Clone`。所以编译器会尝试通过自动搜索来调用。在这种情况下，该函数的签名是`fn clone(&T) -> &T`，因为`Self = &T`。编译器看到`&T: Clone`，然后推断出`cloned: &T`。

下面是另一个例子，自动搜索行为被用来创造一些微妙的效果：

```rust
# use std::sync::Arc;
#
#[derive(Clone)]
struct Container<T>(Arc<T>);

fn clone_containers<T>(foo: &Container<i32>, bar: &Container<T>) {
    let foo_cloned = foo.clone();
    let bar_cloned = bar.clone();
}
```

`foo_cloned`和`bar_cloned`是什么类型？我们知道，`Container<i32>: Clone`，所以编译器按值调用`clone`，得到`foo_cloned: Container<i32>`。然而，`bar_cloned`实际上有`&Container<T>`类型。这肯定是不合理的——我们给`Container`添加了`#[derive(Clone)]`，所以它必须实现`Clone`! 仔细看看，由`derive`宏产生的代码是（大致）：

```rust,ignore
impl<T> Clone for Container<T> where T: Clone {
    fn clone(&self) -> Self {
        Self(Arc::clone(&self.0))
    }
}
```

派生的`Clone`实现是[只在`T: Clone`的地方定义][clone]，所以没有`Container<T>`的实现。`Clone`在一般的`T`上没有实现。编译器接着查看`&Container<T>`是否实现了`Clone`，最终发现它实现了。因此，它推断出`clone`是由 autoref 调用的，所以`bar_cloned`的类型是`&Container<T>`。

我们可以通过手动实现`Clone`而不需要`T: Clone`来解决这个问题：

```rust,ignore
impl<T> Clone for Container<T> {
    fn clone(&self) -> Self {
        Self(Arc::clone(&self.0))
    }
}
```

现在，类型检查器推断出，`bar_cloned: Container<T>`。

[fqs]: https://doc.rust-lang.org/book/ch19-03-advanced-traits.html#fully-qualified-syntax-for-disambiguation-calling-methods-with-the-same-name
[method_lookup]: https://rustc-dev-guide.rust-lang.org/method-lookup.html
[index]: https://doc.rust-lang.org/std/ops/trait.Index.html
[clone]: https://doc.rust-lang.org/std/clone/trait.Clone.html#derivable
