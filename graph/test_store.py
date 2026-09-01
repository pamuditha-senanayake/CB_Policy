from bitemporal_store import BitemporalStore

def test_store():
    store = BitemporalStore()
    
    # Insert v0
    store.insert('loyalty', 0, 'discount==10', 'v0 text', valid_from=0, tx_now=0)
    
    # At tx=300, we learn of v1 starting at 300
    store.invalidate('loyalty', 300, tx_now=300)
    store.insert('loyalty', 1, 'discount==15', 'v1 text', valid_from=300, tx_now=300)
    
    # At tx=600, we rollback to v0
    store.invalidate('loyalty', 600, tx_now=600)
    store.insert('loyalty', 0, 'discount==10', 'v0 text', valid_from=600, tx_now=600) # version 0 again!
    
    # Boundaries
    assert store.as_of('loyalty', 150, 200)['version'] == 0
    assert store.as_of('loyalty', 400, 400)['version'] == 1
    
    # Rollback
    ans = store.as_of('loyalty', 700, 700)
    assert ans['version'] == 0
    
    # Transaction-time audit
    ans_audit = store.as_of('loyalty', 400, 200)
    assert ans_audit['version'] == 0
    
    # Canary
    store.insert('canary', 0, 'cond', 'text', valid_from=0, tx_now=0)
    assert store.as_of('canary', 1000, 1000)['version'] == 0
    assert store.current('canary')['version'] == 0

    print("All store tests passed.")

if __name__ == '__main__':
    test_store()
