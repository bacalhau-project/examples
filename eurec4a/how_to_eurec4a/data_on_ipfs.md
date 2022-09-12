---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# Data on IPFS

We use [IPFS](https://ipfs.io/) to store public data from the field campaign in a decentralized manner in order to increase data availability and accessibility.
Ideally, as a user of the How to EUREC4A book, you'd maybe not even notice that this system is working, because [intake](https://intake.readthedocs.io/en/latest/) handles the details of the data retrieval.

## Access via intake
Currently, the use of IPFS within the How to EUREC4A book is mostly optional and can be enabled by the `use_ipfs` argument of `eurec4a.get_intake_catalog` (it's disabled by default):

```{code-cell} ipython3
import eurec4a
cat = eurec4a.get_intake_catalog(use_ipfs=False)
list(sorted(cat))[:5]
```
This above command returns the first five entries in the [eurec4a-intake catalog](https://github.com/eurec4a/eurec4a-intake/#readme). Most of the data references by this catalog is accessed via the [OPeNDAP](https://www.opendap.org/) protocol from several servers in use by the EUREC4A community.
Let's look how this changes if we enable `use_ipfs`:

```{code-cell} ipython3
cat = eurec4a.get_intake_catalog(use_ipfs=True)
list(sorted(cat))[:5]
```

... we get the same result 😃. Ideally, the resulting intake catalog should behave just as the "classical" counterpart. Apart from a few edge-cases, which often are related to {doc}`netcdf_datatypes`, you should be able to use both catalogs interchangeably, although almost everything behind the scenes works differently.

The IPFS based catalog is auto-generated from the non-IPFS catalog, such that the latest version of the IPFS-based catalog should match the non-IPFS catalog.
However, as the IPFS-based catalog is set up such that each version of the catalog references distributed, immutable copies of the datasets, those datasets stay available even if they are removed from their original storage locations (or the original servers are unavailable).
If datasets in the non-IPFS catalog are updated, this will result in a new version of the IPFS-based catalog, which will then refer to the updated datasets subsequently.

While just the option to have two completely separate ways of accessing the data already improves data availability, our hope would be that accessing data via IPFS would virtually never fail. In order to discuss this further, we'll have to take a deeper look at what IPFS and content addressing actually is.
But before arriving there, we'll have a short detour about which properties we'll want to have for references to our datasets.

````{note}
There's one more option (accessing the intake catalog by content identifier), which will be described in more detail below:

```python
cat = eurec4a.get_intake_catalog(use_ipfs="QmahMN2wgPauHYkkiTGoG2TpPBmj3p5FoYJAq9uE9iXT9N")
```

If the intake catalog is loaded by explicitly stating the content identifier of the catalog, it is ensured that always the same catalog and the same data within the catalog is returned (instead of always returning the newest catalog and datasets). We use this method of accessing the catalog in the book to ensure that our examples are reproducible.
````

## Referencing data

The book is about sharing knowledge on available datasets and analysis methods.
We want to be able to create reproducible analysis scripts (or stories) which may be run and modified by anyone.
While sharing code (e.g. analysis scripts) and explanatory texts is largely solved by version control systems like [git](https://git-scm.com/), sharing data is much more complicated due to the size of the referenced files.
While often it is just undesirable to copy larger files around over and over again, for some datasets it might even be impossible to store them entirely on a laptop.
If we can't just copy data, we need a way of referencing data that is stored elsewhere. A unique and reliable reference ensures the correct retrieval of data for everyone and from everywhere via a code snippet such as the following:

```python
dataset = open_dataset("some reference")
result = do_some_analysis(dataset)
make_a_nice_plot(result)
```

But as it turns out, creating good references which work nicely in this setting can be harder than it seems to be in the first place. We'll want a couple of features which those kinds of references should fulfill to be really useful:

* They should be **global** (i.e. work anywhere on the world)
* They should be **fault tolerant** and **available** (i.e. if a server fails, not everyone's workflows should stop)
* They should be **performant** (i.e. accessing the data should be at least about as fast as downloading them once and access them locally)
* The data behind the reference may not change / must be **immutable** (i.e. if I'm running an analysis, I don't want my result to change without me noticing it, I also want to be able to re-run the analysis at a later point in time to re-evaluate my conclusions)
* They should refer **directly** to the data to be used, such that no manual steps are required. (This is in contrast to DOIs, which [should resolve to a landing page, not directly to the content](https://support.datacite.org/docs/landing-pages#best-practices))
* They should be **easy to use** (it's important that people *want* to use these references, such that dataset creators use datasets in their published form).

Many popular references only provide some of these goals, e.g.:
* *filesystem paths* are not globally available and generally not immutable
* *HTTP-links* are global, but often less performant than local files. They are also not immutable and not by themselves fault tolerant
* *DOIs* don't refer directly to the data, as they are mostly about metadata. In most cases a DOI just forwards to some HTTP link, providing only some contractual guarantees on immutability and availability, but little technical benefits.

There's one unfortunate piece, which all of these references have in common: they always include (implicit or explicit) a server or computing system which is responsible to host the data.
They are references to the **location** of the data, not the **identity** of the data.
This is much like describing the location of a book in a bookshelf (and the location of the bookshelf...) in stead of describing the book's identity by ISBN or author / title.
Referencing by location can become a big problem, if data has to move between locations or important servers fail.
Addressing data by it's content is an approach to remove location information from the references.
Let's see how this concept works:

## Content Addressable Storage

The concept of content addressable storage is based on the idea that identifiers which can be used to reference some content are based on the content itself.
This concept helps with many of the requirements listed above, so let's have a look at some usual properties of content addressable storage.

### Hash functions
Typically, content identifiers are based on a cryptographic hash of the content to be referenced.
Cryptographic hashes are functions which accept an arbitrarily sized stream of bytes and convert them into a fixed sized (relatively short) sequence of bytes.
They are designed such that the output (i.e. the hash value) changes whenever anything of the input changes.
Furthermore, it is extremely unlikely (i.e. practically impossible) to find two different inputs which result in the same hash value.
Python already provides a couple of hash functions, so let's look how a typical hash function (`sha256`) of some values looks like:

```{code-cell} ipython3
from hashlib import sha256
sha256(b"hallo").hexdigest()
```

```{code-cell} ipython3
sha256(b"hello").hexdigest()
```

Two similar (but different) input byte-sequences return completely different hash values.
If we compute a hash value from a longer byte-sequence (e.g. 1000 numbers from a `numpy` array), the resulting hash value is of the same size as before:

```{code-cell} ipython3
import numpy as np
sha256(np.arange(1000)).hexdigest()
```

And if we redo a hash-computation of the same input, we'll get exactly the same output as before:

```{code-cell} ipython3
sha256(b"hello").hexdigest()
```

Furthermore, if you do this hash computation on your own machine, you'll obtain exactly the same value as shown here.
This property can be used for **verification**: if one knows the correct hash-value of some newly retrieved data, one can re-compute the hash-value from the data and check if it matches the known value.
If the check fails, we know that the data was modified in between.

Content addressable stores usually use such hash values to reference the stored data, thus when retrieving data from such a store, one already knows the hash and can check if the retrieved content was returned unmodified.

### Immutability

As a direct consequence of using hashes as references, it is not possible to change data behind this kind of reference.
The data behind a reference is **immutable**.
Instead, whenever something is changed, a new (different) reference will be created. 
Immutability not only solves the request for non-changing data behind a reference, it also facilitates distributed hosting of data.
Any machine hosting a dataset can either have or not have the dataset, but it can not have the dataset in a different (or old) variant, because that would be a different dataset, referenced by  a different hash.


### Basic content addressable store

Let's have a look at how a basic content addressable store could be implemented:

```{code-cell} ipython3
class CAStore:
    def __init__(self):
        self._store = {}
    def put(self, content):
        key = sha256(content).hexdigest()
        self._store[key] = content
        return key
    def get(self, key):
        return self._store[key]
```
The store is just a wrapper around a dictionary, with the crucial change that a `put` doesn't have the `key` as an argument, but as a return value.
Let's try it out:


```{code-cell} ipython3
store = CAStore()
k_hello = store.put(b"hello")
k_Hello = store.put(store.get(k_hello).replace(b"h", b"H"))
```

As we know the key of `hello` from before, we can now use that to ask our store for that value:

```{code-cell} ipython3
store.get('2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824')
```

Note that the modified version of `hello` with a capital `H` is also in the store, but of course under a different key:

```{code-cell} ipython3
store.get(k_Hello)
```

Finding out the value of `k_Hello` is left as an exercise to the reader 😃.

Another interesting feature is automatic de-duplication.
Let's see what happens to the amount of data stored before and after putting `hello` again:

```{code-cell} ipython3
print(f"item count before put: {len(store._store)}")
store.put(b"hello")
print(f"item count after put: {len(store._store)}")
```

Because every item is stored under it's own hash, identical items will only be stored once.

So a content addressable store allows to `put` and `get` some content.
Content which is already in the store won't change over time.
If two different stores contain the same content, that same content will be retrievable under the same identifier, independent of the machine hosting the store.

So far, we've got an **immutable** store, which gives **direct** access to the content stored.
As we've not yet built in any means of external communication (that's for later), the store is only local.
But as a local store, access is as **performant** as any other local key-based access method would be (with automatic de-duplication as potential advantage in terms of required storage).

If some requested identifier is not available on a store, it will simply fail (and not return something different):


```{code-cell} ipython3
---
tags: [raises-exception]
---
store.get('d3751d33f9cd5049c4af2b462735457e4d3baf130bcbb87f389e349fbaeb20b9')  # the key of b"hallo"
```

If there would be a method to find a store on another machine which does contain the missing key, this would open the door for a global and fault tolerant content distribution system.
This is where IPFS comes into play.

## What is IPFS?

![](figures/ipfs-logo-text-128-ice.png)

We'll start with a self-description of the [IPFS project](https://ipfs.io/):

> IPFS (the InterPlanetary File System) is a peer-to-peer hypermedia protocol for content addressing. An alternative to the HTTP protocol, IPFS builds on the principles of peer-to-peer networking and content-based addressing to create a decentralized, distributed, and trustless data storage and delivery network. With IPFS, users ask for a file and the system finds and delivers the closest copy without the need to trust a centralized delivery source. In addition to more efficient content distribution, IPFS offers improved security, content integrity, and resistance to third-party tampering.

So, that's quite a bunch of words. How can we relate this to what's written above? And what does this really mean in the context of EUREC4A data and the How to EUREC4A book?


IPFS is a protocol, defining how machines can communicate with each other to exchange content.
To do so, IPFS combines ideas of peer-to-peer networking with content addressing.
In IPFS, each participating node (there's no distinction between clients, servers or the like), will have it's own content addressable store, which behaves much like what we've seen above.
On top of that, each node communicates with other nodes (the peers) asking for and exchanging content based  on hash-based content identifiers (CIDs).
Whenever a requested CID is not available in the local store, IPFS will ask the connected peers if they can deliver the requested content.
If any of the nodes has the requested content, it is delivered to the local node and to the user.
Because it is enough if *any* peer answers the request, simply running multiple machines storing the same content creates **fault tolerance** and better **availability** for the requested content.
Requests will automatically be answered by the remaining machines if one machine goes offline.
Furthermore, the correctness of the content can be verified using the hash as described above.
Thus, one doesn't have to trust any of those peers and anyone can join the network freely, potentially providing additional redundancy without the risk of modifying existing content.

Of course, a single node can't be connected to the entire internet, so there must be an efficient mechanism to find peers having the requested CID without being connected to the peer.
For this purpose, IPFS builds a [distributed hash table](https://en.wikipedia.org/wiki/Distributed_hash_table) (DHT) as common in other peer-to-peer networks across all participating nodes.
The DHT contains a mapping from CID to node addresses.
Using this DHT, it is possible to find more peers which have the requested content stored without the need of any central registry.
Once connected to one of those newly discovered nodes, content can be retrieved from those nodes as above.
Because the DHT enables a **global** search for nodes which have the content behind a CID stored, it indeed becomes possible to use CIDs as a global identifier.

Whenever a node retrieves data behind a CID, it may keep a copy of that data for a while in a local cache.
Subsequent requests to the same CID can then be fulfilled locally.
Thus if a node is running on the computer of the user of a dataset, a first request to a dataset identified by CID will download the data, while future requests will operate on a local copy, leading to good access **performance** as mentioned in the beginning.


### ease of use
Ease of use is probably the most difficult to quantify.
We've seen that while the `put` function looks different, the `get` function essentially looks the same as for any key-value store: we hand in a key and get a value.
Accordingly, read access to the data should be very similar on IPFS when compared to other methods like a file-system or object store.

#### reading data
The [`zarr`](https://zarr.readthedocs.io/) and [`intake`](https://intake.readthedocs.io/) libraries both use [`fsspec`](https://filesystem-spec.readthedocs.io) to access file-like resources (e.g. local files, HTTP links, cloud storage, zip archives and more) in a common way.
As the EUREC4A intake catalog builds on `zarr` and `intake`, IPFS can be supported relatively easily through an `fsspec` backend.
This is the purpose of `ipfsspec`, which we'll have to install in addition to your usual python packages:

```
pip install ipfsspec
```

Afterwards, we can use links of the form `ipfs://<CID>` or `ipfs://<CID>/some/path/within/the/content` wherever `fsspec` is used to access files.
In particular, it is possible to open intake catalogs and zarr datasets from those references, which is exactly what happens behind the scenes when opening the EUREC4A intake catalog using `use_ipfs`:

```python
cat = eurec4a.get_intake_catalog(use_ipfs=True)
```

For better **performance**, you should also run an [IPFS node](https://ipfs.io/#install) on the machine accessing the data.
`ipfsspec` will detect the presence of the node and will start requesting content through the local node in stead of using [public gateways](https://docs.ipfs.io/concepts/ipfs-gateway/#gateway-providers).
This mode of operation will not only enable local caching, but also will request data from nearby peers (e.g. colleagues next door) should they already have the content.

#### writing data

As `put` works differently (we can only hand in content and not a key and content), adding data to a content addressable store must work a bit differently as compared to other stores.
Let's see how we can do this.

If a local node is running on your machine, you can also add data to IPFS.
E.g. if a folder containing a dataset in zarr format should be added, you can do so by running:

```bash
ipfs add -r -H --raw-leaves dataset.zarr
```

which will return a CID, which can subsequently be used to access the data, e.g. by opening it like:

```python
ds = xr.open_zarr("ipfs://CID")
```

```{note}
IPFS is a **public** network. Thus data added to IPFS will potentially be publicly available after adding it to your local node.
```

After adding the dataset to your local node, it can be accessed by others, but this may be slow initially, as your machine is the only one hosting it.
If you add your dataset to the EUREC4A intake catalog, we'll retrieve the dataset and store additional copies on servers with good internet connectivity, which will improve dataset retrieval speeds.
Of course, you can also setup your own nodes for dataset hosting or have a look at [pinning services](https://docs.ipfs.io/concepts/persistence/#pinning-services).
