import sys
import numpy as np
import matplotlib as mpl

mpl.use("TKAgg")
import matplotlib.pyplot as plt
import gym
import torch
import torch.nn as nn

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def main():
    seed = 0 if len(sys.argv) == 1 else int(sys.argv[1])

    # Task setup block starts
    # Do not change
    env = gym.make('CartPole-v1')
    env.seed(seed)
    o_dim = env.observation_space.shape[0]
    a_dim = env.action_space.n
    # Task setup block end

    # Learner setup block
    torch.manual_seed(seed)

    ####### Start
    # Actor & Critic networks
    actor = nn.Sequential(
        nn.Linear(o_dim, 32),
        nn.ReLU(),
        nn.Linear(32, 16),
        nn.ReLU(),
        nn.Linear(16, a_dim),
        nn.Softmax(dim=-1))

    critic = nn.Sequential(
        nn.Linear(o_dim, 32),
        nn.ReLU(),
        nn.Linear(32, 32),
        nn.ReLU(),
        nn.Linear(32, 1))

    # Actor & Critic optimizers
    opt_act = torch.optim.Adam(actor.parameters(), lr=0.001)
    opt_cri = torch.optim.Adam(critic.parameters(), lr=0.001)

    # Actionspace is [0, 1] in cartpole
    action_space = np.arange(env.action_space.n)

    # Lambda return for an episode
    def lambda_return_naive(lam, gamma, s_vec, r_vec, a_critic):
        G_n = []
        G_l = []
        T = len(r_vec)

        for t in range(0, T):
            # First calculate all the n-step returns for given t, and then append G_t
            for n in range(1, T - t):
                G_n.append(sum(np.multiply(r_vec[t:(t + n)], [gamma ** j for j in range(0, n)])) + a_critic(
                    torch.FloatTensor(s_vec[t + n - 1])).data)  # .data to remove grad req
            # G_t
            G_n.append(sum(np.multiply(r_vec[t:], [gamma ** (j-1) for j in range(1, T-t+1)])))

            # the lambda return for t
            G_l.append((1-lam)*sum(np.multiply(G_n[:-1], [lam ** j for j in range(0, T-t-1)])) + G_n[-1]*lam**(T-t-1))
            G_n = []
        return G_l

    # lambda return using recursive formula
    def lambda_return(lam, gamma, s_vec, r_vec, a_critic):
        # R_vec = [R1, R2, ..., R_T]
        # S_vec = [s0, s1, ...., S_(T-1)]
        G_l = []
        T = len(r_vec) - 1
        G_l.append(r_vec[-1]) #G^l_(T-1) = R_T

        while T > 0:
            G_l.append(gamma*(1-lam)*a_critic(torch.FloatTensor(s_vec[T-1])).squeeze().detach().numpy() + r_vec[T] + gamma*lam*G_l[-1])
            T -= 1

        return G_l[::-1]

    # Actor-Critic parameters
    gamma = 1
    lam = 1

    # Params for batch learning
    k = 1  # episode number
    K = 30  # nb episodes in each batch

    # State, Action, Reward, Return (to be emptied after each episode)
    s_epi = []
    a_epi = []
    r_epi = []
    g_epi = []

    # State, Action, Reward, Return (to be emptied after each batch)
    s_batch = []
    a_batch = []
    r_batch = []
    g_batch = []
    ####### End

    # Experiment block starts
    ret = 0
    rets = []
    avgrets = []
    o = env.reset()
    num_steps = 500000
    checkpoint = 10000
    for steps in range(num_steps):

        # Select an action
        ####### Start
        a = np.random.choice(a=action_space, p=actor(torch.FloatTensor(o)).detach().numpy())
        ####### End

        # Observe
        op, r, done, infos = env.step(a)

        # Learn
        ####### Start
        # Here goes your learning update
        s_epi.append(o)
        a_epi.append(a)
        r_epi.append(r)

        if done:

            # Episode Lambda returns
            g_epi = lambda_return(lam, gamma, s_epi, r_epi, critic)

            # Adding episode to batch
            s_batch.extend(s_epi)
            a_batch.extend(a_epi)
            g_batch.extend(g_epi)

            # Clear after each episode
            s_epi = []
            a_epi = []
            r_epi = []
            g_epi = []

            # If episode is over and B episodes added to batch, then learn
            if k % K == 0:
                s_batch = torch.FloatTensor(s_batch)
                a_batch = torch.LongTensor(a_batch)
                g_batch = torch.FloatTensor(g_batch)
                h_batch_prime = g_batch - critic(torch.FloatTensor(s_batch))  # take grad on this
                h_batch = h_batch_prime.data  # do not take grad on this

                # update actor....
                log_policy = torch.log(actor(torch.FloatTensor(s_batch)))
                sampled_log_policy = h_batch * torch.gather(log_policy, 1, a_batch.unsqueeze(1)).squeeze()
                loss_act = -sampled_log_policy.mean()
                opt_act.zero_grad()
                loss_act.backward()
                opt_act.step()

                # update critic...
                loss_crit = (h_batch_prime ** 2).mean()
                opt_cri.zero_grad()
                loss_crit.backward()
                opt_cri.step()

                # Emptying after each batch
                s_batch = []
                a_batch = []
                r_batch = []
                g_batch = []
                h_batch_prime = []
                h_batch = []

            # move onto next episode
            k += 1

        # Learning ends

        # Update environment
        o = op
        ####### End

        # Log
        ret += r
        if done:
            rets.append(ret)
            ret = 0
            o = env.reset()

        if (steps + 1) % checkpoint == 0:
            avgrets.append(np.mean(rets))
            rets = []
            plt.clf()
            plt.plot(range(checkpoint, (steps + 1) + checkpoint, checkpoint), avgrets)
            plt.pause(0.001)
    name = sys.argv[0].split('.')[-2].split('_')[-1]
    data = np.zeros((2, len(avgrets)))
    data[0] = range(checkpoint, num_steps + 1, checkpoint)
    data[1] = avgrets
    np.savetxt(name + str(seed) + ".txt", data)
    #plt.show()


if __name__ == "__main__":
    main()
