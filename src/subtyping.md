# 子类型化和变异性

子类型是一种类型之间的关系，它允许静态类型语言更加灵活和宽松一些。

Rust 中的子类型与其他语言的子类型有些不同，这使得它很难给出简单的例子，这是一个问题，因为子类型，尤其是变异性，已经很难正确理解了。即使是编译器编写者也经常把它搞混。

为了保持简单，本节将考虑对 Rust 语言进行一个小的扩展，增加一个新的、更简单的子类型关系。在这个更简单的系统下建立概念和问题后，我们将把它与 Rust 中子类型的实际发生情况联系起来。

这就是我们的简单扩展，*Objective Rust*，具有三个新的类型：

```rust
trait Animal {
    fn snuggle(&self);
    fn eat(&mut self);
}

trait Cat: Animal {
    fn meow(&self);
}

trait Dog: Animal {
    fn bark(&self);
}
```

但与普通 trait 不同的是，我们可以像结构体一样，将它们作为具体的、有确定大小的类型使用。

现在，假设我们有一个非常简单的函数，它接收一个 Animal，像这样：

<!-- ignore: simplified code -->
```rust,ignore
fn love(pet: Animal) {
    pet.snuggle();
}
```

默认情况下，静态类型必须*完全*匹配，程序才能被编译。因此，这段代码不会被编译：

<!-- ignore: simplified code -->
```rust,ignore
let mr_snuggles: Cat = ...;
love(mr_snuggles);         // 错误：期待是一个动物，实际上却是猫
```

Snuggles 先生是一只猫，而猫并不能够*精确地*认为和动物相等，所以我们不能爱他！。😿

这很烦人，因为猫*是*动物，它们支持动物所支持的所有操作，所以从直觉上讲，“爱”不应该关心我们是否把“猫”传递给它。我们应该能够**忘记**我们的“猫”的非动物部分，因为它们不是爱它的必要条件。

这正是*subtyping*所要解决的问题。因为猫是动物，并且猫有**更多**特征，所以我们说猫是动物的*子类型*（因为猫是所有动物的*子集*）。等价地，我们说动物是猫的*超集*。有了子类型，我们可以用一个简单的规则来调整我们过于严格的静态类型系统：在任何期望有`T`类型的值的地方，我们也将接受`T`的子类型的值。

或者更具体地说：在任何期望有动物的地方，猫或狗也可以适用。

正如我们将在本节的其余部分看到的，子类型比这要复杂和微妙得多，但这个简单的规则是一个非常好的 99% 的直觉。除非你写的是不安全的代码，否则编译器会自动为你处理所有的边界情况。

但这是死灵书，我们在写不安全的代码，所以我们需要了解这东西到底是怎么运作的，以及我们会如何把它给搞炸咯。

最核心的问题是，这个规则如果我们不假思索地应用后，会导致*喵喵狗*。也就是说，我们可以说服别人，狗实际上是猫。这完全破坏了我们的静态类型系统的结构，使其比不可用还要糟糕（并导致未定义行为）：

下面是一个简单的例子，当我们以完全纯粹的“查找和替换”方式应用子类型时，这种情况就会发生：

<!-- ignore: simplified code -->
```rust,ignore
fn evil_feeder(pet: &mut Animal) {
    let spike: Dog = ...;

    // `pet` 是一个动物，而狗是动物的子类型，
    // 所以这里应该是正确的，对吗...?
    *pet = spike;
}

fn main() {
    let mut mr_snuggles: Cat = ...;
    evil_feeder(&mut mr_snuggles);  // 将 mr_snuggles 替换为狗
    mr_snuggles.meow();             // 哇，这里发出了狗叫："MEOWING DOG!"！
}
```

显然，我们需要一个比“查找和替换”更强大的系统。这个系统就是*变异性（variance）*，它是一套管理子类型应该如何组成的规则。最重要的是，变量定义了应该禁用子类型的情况。

但在我们讨论变异性之前，让我们先来看看 Rust 中子类型实际上发生了什么：*lifetimes*!

> 注意：生命周期的类型化是一个相当随意的构造，有些人也许不同意这种设计。然而，它将生命周期和类型统一在一起，简化了我们的分析。

生命周期只是代码的作用域，而作用域可以通过*包含*（超越）的关系来部分排序。生命周期的子类型是指这种关系：如果`'big: 'small`（“big 包含 small”或“big outlives small”），那么`'big`就是`'small`的一个子类型。这是一个很大的混乱来源，因为对许多人来说，它似乎是倒过来的：大区域是小区域的*子类型*。但是如果你考虑我们的动物例子，这就说得通了：猫是一种动物*并且拥有更多特征*，就像`'big`是`'small`的更多一样。

换句话说，如果有人想要一个能活到`'small`的引用，通常他们的意思是，他们想要一个至少能活到`'small`的引用。他们实际上并不关心生命周期是否完全匹配。所以，我们应该可以**忘记**某个东西的生命周期是`'big`，而只记得它的生命周期是`'small`。

生命周期的喵喵狗问题将导致我们能够将一个短生命周期的引用存储在一个期望长生命周期的地方，创造一个悬空的引用，并让我们产生释放后使用（use-after-free）。

值得注意的是，`'static`，即永远的生命周期，是每个生命周期的子类型，因为根据定义，它比所有的东西都要长。我们将在后面的例子中使用这种关系，以使它们尽可能的简单。

说了这么多，我们仍然不知道如何实际*使用*生命周期的子类型，因为没有任何东西具有`'a`的类型。生命周期只作为一些更大的类型的一部分出现，如`&'a u32`或`IterMut<'a, u32>`。为了应用生命周期子类型，我们需要知道如何组成子类型。因此，我们需要*变异*。

## 变异

Variance 是事情变得有点复杂的地方。

变异是*类型构造器*相对于其参数的一种属性。Rust 中的类型构造器是任何具有非绑定参数的通用类型。例如，`Vec`是一个类型构造器，它接受一个类型`T`并返回`Vec<T>`。`&`和`&mut`是类型构造器，接受两个输入：一个生命周期，和一个指向的类型。

> 注意：为方便起见，我们经常将`F<T>`称为类型构造器，只是为了方便我们谈论`T`。希望这在上下文中是清楚的。

类型构造器 F 的*变异*是指其输入的子类型如何影响其输出的子类型。在 Rust 中，有三种变异，假设给定两个类型`Sub`和`Super`，其中`Sub`是`Super`的一个子类型：

* 如果`F<Sub>`是`F<Super>`的一个子类型，则`F`是*协变的*（子类型化`传递`）
* 如果`F<Super>`是`F<Sub>`的一个子类型，则`F`是*逆变的*（子类型化是`翻转`）
* 针对其他情况，`F`都认为是*不变的*（不存在子类型关系）

如果`F`有多个类型参数，我们可以通过说，例如：`F<T, U>`对`T`是协变的，对`U`是不变的，来谈论各个变异性。

要记住，针对变异性来说，我们大部分情况下讨论的都是协变。几乎所有对变异性的讨论都是在某物是否应该是协变或不变。实际上，在 Rust 中逆变是相当困难的，尽管它确实存在。

下面是一个重要的变异性表，本节的其余部分将专门用来解释：

|   |                 |     'a    |         T         |     U     |
|---|-----------------|:---------:|:-----------------:|:---------:|
| * | `&'a T `        | covariant | covariant         |           |
| * | `&'a mut T`     | covariant | invariant         |           |
| * | `Box<T>`        |           | covariant         |           |
|   | `Vec<T>`        |           | covariant         |           |
| * | `UnsafeCell<T>` |           | invariant         |           |
|   | `Cell<T>`       |           | invariant         |           |
| * | `fn(T) -> U`    |           | **contra**variant | covariant |
|   | `*const T`      |           | covariant         |           |
|   | `*mut T`        |           | invariant         |           |

带有 \* 的类型是我们要关注的，因为它们在某种意义上是“基础”的，所有其他的类型可以通过与其他类型的类比来理解：

* `Vec<T>`和所有其他拥有指针和集合的类型遵循与`Box<T>`相同的逻辑
* `Cell<T>`和所有其他内部可变型遵循与`UnsafeCell<T>`相同的逻辑
* `*const T`遵循`&T`的逻辑
* `*mut T`遵循`&mut T`的逻辑（或`UnsafeCell<T>`）

关于更多的类型，请参见参考资料上的[“变异性”部分][variance-table]。

[variance-table]: https://doc.rust-lang.org/reference/subtyping.html#variance

> 注意：语言中*唯一*的逆变是函数的参数，这就是为什么它在实践中真的不怎么出现。调用逆变涉及到高阶编程与函数指针的关系，这些指针采用具有特定生命周期的引用（与通常的“任何生命周期”相反，这涉及到高阶生命周期，它独立于子类型的工作）。

好了，类型理论已经足够了！让我们试着将变异性的概念应用于 Rust，并看看一些例子：

首先，让我们重温一下喵喵叫的狗的例子：

<!-- ignore: simplified code -->
```rust,ignore
fn evil_feeder(pet: &mut Animal) {
    let spike: Dog = ...;

    // `pet` 是一个 Animal，而 Dog 是 Animal 的子类型
    // 所以这里应该是正确的，对吗...?
    *pet = spike;
}

fn main() {
    let mut mr_snuggles: Cat = ...;
    evil_feeder(&mut mr_snuggles);  // 将 mr_snuggles 替换为 Dog
    mr_snuggles.meow();             // 哇，这里发出了狗叫："MEOWING DOG!"！
}
```

如果我们看一下我们的变异表，我们会发现`&mut T`在`T`上是*不变*的。事实证明，这完全解决了问题! 有了不变性，猫是动物的一个子类型这一事实并不重要；`&mut Cat`仍然不是`&mut Animal`的一个子类型。然后，静态类型检查器将正确地阻止我们将猫传入`evil_feeder`。

子类型的合理性是基于这样的想法：忘记不必要的细节是可以的。但是对于引用来说，总是有人记得这些细节：被引用的值。这个值希望这些细节一直是真实的，如果它的期望被违反，可能会有不正确的行为。

使`&mut T`对`T`具有协变性的问题是，*当我们不记得它的所有约束时*，它给了我们修改原始值的权力。因此，我们可以让一个人在确定自己仍然有一只猫的时候拥有一只狗。

有了这一点，我们可以很容易地看到为什么`&T`在`T`上的协变是安全的：它不让你修改值，只让你读取它。如果没有任何可以修改的方法，我们就没有办法去把事情搞砸。我们也可以看到为什么`UnsafeCell`和所有其他内部可变型必须是不变的：它们使`&T`像`&mut T`一样工作！

那么，引用的生命周期到底是什么？为什么两种引用在其生命周期内都是协变是安全的？嗯，这里有一个双管齐下的论点：

首先，基于生命周期的引用子类型是 *Rust 中子类型的全部内容*。我们有子类型的唯一原因是，我们可以将长生命周期的东西传递给短生命周期的东西，所以它最好是有效的。

第二，更重要的是，生命周期只是引用本身的一部分。被引用的值是共享的，这就是为什么只在一个地方（引用）修改该类型会导致问题。但是如果你在把一个引用交给别人的时候缩小了它的生命周期，那么这个生命周期信息就不会以任何方式共享。现在有两个独立的引用并且都具有独立的生命周期，没有办法用另一个引用的生命周期来干扰原始引用的生命周期。

或者说，搞乱某人的生命周期的唯一方法是建立一只喵喵叫的狗。但是如果你想造一只喵喵狗，生命周期就应该被包裹在一个不变的类型中，防止生命周期被缩减。为了更好地理解这一点，让我们把喵喵狗的问题移植到真正的 Rust 上。

在喵星人的问题中，我们把一个子类型（Cat），转换成一个超类型（Animal），然后利用这个事实，用一个满足超类型但不满足子类型（Dog）的约束的值来覆盖这个子类型。

所以，对于生命周期，我们想把一个长生命周期的东西，转换成一个短生命周期的东西，然后利用这个事实把一个生命周期不够长的东西写到期望长生命周期的地方。

比如：

```rust,compile_fail
fn evil_feeder<T>(input: &mut T, val: T) {
    *input = val;
}

fn main() {
    let mut mr_snuggles: &'static str = "meow! :3";  // mr. snuggles forever!!
    {
        let spike = String::from("bark! >:V");
        let spike_str: &str = &spike;                // 仅仅在这个代码块存在
        evil_feeder(&mut mr_snuggles, spike_str);    // 恶魔降临！
    }
    println!("{}", mr_snuggles);                     // 内存释放后使用？
}
```

当我们运行这个时，我们会得到什么？

```text
error[E0597]: `spike` does not live long enough
  --> src/main.rs:9:31
   |
6  |     let mut mr_snuggles: &'static str = "meow! :3";  // mr. snuggles forever!!
   |                          ------------ type annotation requires that `spike` is borrowed for `'static`
...
9  |         let spike_str: &str = &spike;                // 仅在这个代码块存活
   |                               ^^^^^^ borrowed value does not live long enough
10 |         evil_feeder(&mut mr_snuggles, spike_str);    // 恶魔降临！
11 |     }
   |     - `spike` dropped here while still borrowed
```

意料之中，编译肯定挂了! 让我们详细分析一下这里发生了什么：

首先让我们看一下新的`evil_feeder`函数：

```rust
fn evil_feeder<T>(input: &mut T, val: T) {
    *input = val;
}
```

它所做的就是接受一个可变的引用和一个值，并用它来覆盖引用。这个函数的重要之处在于，它创建了一个类型平等的约束。它在其签名中明确指出，引用和值必须是*完全相同的*类型。

同时，在调用者中，我们传入了`&mut &'static str`和`&'spike_str str`。

因为`&mut T`在`T`上是不变的，编译器认为它不能对第一个参数应用任何子类型，所以`T`必须正好是`&'static str`。

另一个参数只是一个`&'a str`，它*是*对`'a`的协变。所以编译器采用了一个约束条件：`&'spike_str str`必须是`&'static str`（包括）的子类型，这反过来意味着`'spike_str`必须是`'static`（包括）的子类型。也就是说，`'spike_str`必须包含`'static`。但是只有一种东西包含`'static`——`'static`本身。

这就是为什么当我们试图将`&spike`赋值给`spike_str`时得到一个错误。编译器倒推了一下，认为`spike_str`必须永远存在，而`&spike`根本不可能存在那么久。

因此，尽管引用在它们的生命周期内是不变的，但只要它们被放到一个可能会对它们造成不良影响的上下文中，它们就“继承”了不变性。在这种情况下，当我们把引用放在`&mut T`中时，我们就继承了不变性。

事实证明，为什么 Box（以及 Vec、Hashmap 等）可以是协变的，这个论点与生命周期可以是协变的论点非常相似：只要你试图把它们塞进像可变引用这样的东西里，它们就会继承不变性，你就不会做任何坏事。

然而，Box 使我们更容易关注在我们之前忽略的引用的值方面：

不像很多语言允许值在任何时候都可以自由别名，Rust 有一个非常严格的规则：如果你想要修改这个值的或者移动这个值，那么你需要保证是唯一可以访问它的人。

例如以下的代码：

<!-- ignore: simplified code -->
```rust,ignore
let mr_snuggles: Box<Cat> = ..;
let spike: Box<Dog> = ..;

let mut pet: Box<Animal>;
pet = mr_snuggles;
pet = spike;
```

我们忘记了`mr_snuggles`是一只猫，或者我们用一只狗重写了他，这一点都没有问题，因为一旦我们把`mr_snuggles`移到一个只知道他是动物的变量上，**我们就破坏了宇宙中唯一记得他是一只猫的东西**了！这就是为什么我们的引用是不可变的。

相对于不可变引用是协变的因为它们不会让你改变任何东西，你拥有所有权的值也是协变的因为它们*会*让你改变任何东西。旧位置和新位置之间没有任何联系。值的 subtyping 是一种不可逆的信息破坏行为，如果没有任何关于事物过去如何的记忆，就没有人可以被骗去根据那些旧的信息行事。

好了，接下来我们只剩下一件事要解释了：函数指针。

为了理解为什么`fn(T) -> U`应该是对`U`的协变，让我们看以下函数签名：

<!-- ignore: simplified code -->
```rust,ignore
fn get_animal() -> Animal;
```

这个函数声称要产生一个动物。因此，提供一个具有以下签名的函数是完全有效的：

<!-- ignore: simplified code -->
```rust,ignore
fn get_animal() -> Cat;
```

毕竟，猫是动物，所以总是产生一只猫是产生动物的一个完全有效的方法。或者把它与真正的 Rust 联系起来：如果我们需要一个函数来产生`'short`生命周期的东西，那么它产生`'long`生命周期的东西是完全可以的。

然而，同样的逻辑并不适用于*函数参数*。假设我们想要用

<!-- ignore: simplified code -->
```rust,ignore
fn handle_animal(Cat);
```

满足以下约束：

<!-- ignore: simplified code -->
```rust,ignore
fn handle_animal(Animal);
```

第二个函数可以接受 Dogs，但第一个函数绝对不行。协变在这里不起作用。但如果我们把它反一反，它实际上是*有效的*如果我们需要一个可以处理猫的函数，那么一个可以处理*任何*动物的函数肯定也可以工作。或者把它与真正的 Rust 联系起来：如果我们需要一个可以处理任何至少`'long`生命周期的东西的函数，那么它完全可以处理任何至少`'short`生命周期的东西。

这就是为什么函数类型，与语言中的其他东西不同，在它们的参数上是**逆变**的。

现在，对于标准库提供的类型来说，这一切都很好，但对于*你*定义的类型来说，如何确定变异性呢？非正式地来看，一个结构继承了其字段的变异性。如果一个结构`MyType`有一个通用参数`A`，用于字段`a`，那么 MyType 对`A`的变异性正好是`a`对`A`的变异性。

然而，如果`A`被用于多个字段：

* 如果所有对`A`的使用都是协变的，那么 MyType 对`A`也是协变的
* 如果所有对`A`的使用都是逆变的，那么 MyType 对`A`也是逆变的
* 否则，MyType 在`A`上是不变的

```rust
use std::cell::Cell;

struct MyType<'a, 'b, A: 'a, B: 'b, C, D, E, F, G, H, In, Out, Mixed> {
    a: &'a A,     // covariant over 'a and A
    b: &'b mut B, // covariant over 'b and invariant over B

    c: *const C,  // covariant over C
    d: *mut D,    // invariant over D

    e: E,         // covariant over E
    f: Vec<F>,    // covariant over F
    g: Cell<G>,   // invariant over G

    h1: H,        // would also be covariant over H except...
    h2: Cell<H>,  // invariant over H, because invariance wins all conflicts

    i: fn(In) -> Out,       // contravariant over In, covariant over Out

    k1: fn(Mixed) -> usize, // would be contravariant over Mixed except..
    k2: Mixed,              // invariant over Mixed, because invariance wins all conflicts
}
```
